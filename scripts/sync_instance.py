"""Forward sync, main -> this instance. Run inside an instance checkout
(instance.env present, e.g. ~/work/ose_sensalis).

Merges origin/main into the instance branch, restarts the instance service,
and compares per-test outcomes and pinned smoke-query rankings against the
pre-merge baseline. Any regression -> hard reset to the pre-merge commit and
restart (the tree is verified clean before starting, so nothing else is lost).

Refuses to merge when the instance branch carries shared-code changes that are
not on main: those must go through scripts/promote_check.py first.

Exit codes: 0 synced or already up to date, 3 shared-code divergence,
4 merge conflict, 5 regression (rolled back), 6 precondition failed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx  # noqa: E402

from config import REPO_ROOT, get_settings  # noqa: E402
from instance_sync import compare_tests, load_junit, shared_paths  # noqa: E402

LOG_PATH = REPO_ROOT / "log" / "sync_instance.log"
SYNC_IDENTITY = ["-c", "user.name=OSE instance sync", "-c", "user.email=ose-sync@sensalis-node"]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=check)


def changed_since(source: str) -> list[str]:
    """Paths the instance branch changed relative to the source ref. Diffs the
    merged tree against the source tree, not merge-base..HEAD: once main is
    merged in, main's own changes would otherwise count as instance changes."""
    if git("merge-base", "--is-ancestor", source, "HEAD", check=False).returncode == 0:
        return [p for p in git("diff", "--name-only", source, "HEAD").stdout.splitlines() if p]
    base = git("merge-base", "HEAD", source).stdout.strip()
    return [p for p in git("diff", "--name-only", base, "HEAD").stdout.splitlines() if p]


def run_tests(junit_path: Path) -> dict[str, str]:
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--ignore=tests/eval",
         "--ignore=tests/answer", f"--junitxml={junit_path}"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=1200,
    )
    return load_junit(junit_path)


def wait_healthy(settings, timeout_s: int = 120) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if httpx.get(f"{settings.api_base_url}/health", timeout=5).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def smoke_rankings(settings) -> dict[str, list[str]]:
    out = {}
    for q in [settings.smoke_query, *settings.sync_smoke_queries]:
        r = httpx.get(f"{settings.api_base_url}/search", params={"q": q, "k": 5}, timeout=60)
        r.raise_for_status()
        out[q] = [h["doc_id"] for h in r.json()["hits"]]
    return out


def restart(settings) -> bool:
    subprocess.run(["systemctl", "--user", "restart", settings.service_name], capture_output=True, text=True)
    return wait_healthy(settings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-ref", default="origin/main")
    parser.add_argument("--accept-ranking-changes", action="store_true",
                        help="don't treat changed smoke-query rankings as a regression (human-reviewed syncs only)")
    args = parser.parse_args(argv)
    settings = get_settings()

    if settings.instance_branch == "main":
        log("PRECONDITION: this checkout is not an instance (instance_branch=main)")
        return 6
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != settings.instance_branch:
        log(f"PRECONDITION: on branch {branch!r}, expected {settings.instance_branch!r}")
        return 6
    if git("status", "--porcelain").stdout.strip():
        log("PRECONDITION: working tree not clean")
        return 6

    if args.source_ref.startswith("origin/"):
        git("fetch", "-q", "origin")
    source = git("rev-parse", args.source_ref).stdout.strip()
    # Checked before "up to date": an instance that already contains main can
    # still carry unpromoted shared-code changes, and those must surface.
    divergent = shared_paths(changed_since(source), settings.instance_paths)
    if divergent:
        log(f"DIVERGENT: {settings.instance_name} changes shared paths not on main, not merging: {divergent} "
            f"-- run scripts/promote_check.py")
        return 3
    if git("merge-base", "--is-ancestor", source, "HEAD", check=False).returncode == 0:
        log(f"UP-TO-DATE: {settings.instance_name} already contains {args.source_ref} ({source[:8]})")
        return 0

    pre = git("rev-parse", "HEAD").stdout.strip()
    behind = git("rev-list", "--count", f"HEAD..{source}").stdout.strip()
    log(f"SYNC START: {settings.instance_name} {pre[:8]} is {behind} commit(s) behind {args.source_ref} ({source[:8]})")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if not wait_healthy(settings, timeout_s=10):
            log("PRECONDITION: instance service not healthy before sync")
            return 6
        rankings_before = smoke_rankings(settings)
        tests_before = run_tests(tmp / "before.xml")

        merge = git(*SYNC_IDENTITY, "merge", "--no-ff", "-m",
                    f"Sync instance {settings.instance_name} with {args.source_ref} ({source[:8]})", source, check=False)
        if merge.returncode != 0:
            git("merge", "--abort", check=False)
            log(f"CONFLICT: merge of {source[:8]} failed, aborted: {merge.stdout.strip()} {merge.stderr.strip()}")
            return 4

        problems = []
        if not restart(settings):
            problems.append("service not healthy after restart")
            rankings_after = {}
        else:
            rankings_after = smoke_rankings(settings)
        tests_after = run_tests(tmp / "after.xml")
        delta = compare_tests(tests_before, tests_after)
        if delta.regressed:
            problems.append(f"tests: newly failing {delta.newly_failing}, new failing {delta.new_failing}")
        if rankings_after and rankings_after != rankings_before and not args.accept_ranking_changes:
            changed_q = {q: {"before": rankings_before[q], "after": rankings_after.get(q)}
                         for q in rankings_before if rankings_before[q] != rankings_after.get(q)}
            problems.append(f"smoke rankings changed: {json.dumps(changed_q)}")

        if problems:
            git("reset", "--hard", pre)
            healthy = restart(settings)
            restored = healthy and smoke_rankings(settings) == rankings_before
            log(f"ROLLED BACK to {pre[:8]} ({'restored OK' if restored else 'ROLLBACK VERIFICATION FAILED'}): "
                f"{'; '.join(problems)}")
            return 5

        log(f"SYNCED: {settings.instance_name} now {git('rev-parse', 'HEAD').stdout.strip()[:8]} contains {source[:8]}; "
            f"tests {sum(v == 'passed' for v in tests_after.values())} passed "
            f"(+{len(delta.new_passing)} new, {len(delta.fixed)} fixed, 0 newly failing); smoke rankings unchanged")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
