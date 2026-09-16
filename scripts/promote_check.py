"""Promotion gate, instance -> main. Run from the OSE source checkout
(~/work/ose, instance_branch=main).

Takes the shared-code part of an instance branch (everything outside that
instance's OSE_INSTANCE_PATHS since it last merged main), applies it to a
throwaway worktree of origin/main, and compares against an unmodified
worktree of origin/main: per-test outcomes plus eval.run on OSE's own
judgment set, both worktrees reading this checkout's live indexes read-only.
PROMOTE = applies cleanly, no test newly fails, nDCG@10 not lower.

Never commits or pushes. On PROMOTE it writes the patch; landing it on main
(from a checkout that can push) is what makes it the source every instance
then syncs from.

Exit codes: 0 PROMOTE or nothing to promote, 2 REJECT, 3 does not apply.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import REPO_ROOT  # noqa: E402
from instance_sync import compare_tests, decide_promotion, load_junit, parse_eval_report, shared_paths  # noqa: E402

LOG_DIR = REPO_ROOT / "log"
# Read-only runtime artifacts eval.run needs; symlinked, never copied or written.
EVAL_DATA = ["tantivy_index", "faiss_index", "vectors.db", "registry.db"]


def run(cmd: list[str], cwd: Path, check: bool = True, env: dict | None = None, timeout: int = 1200):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, env=env, timeout=timeout)


def instance_paths_at(instance_repo: Path, ref: str) -> list[str]:
    text = run(["git", "show", f"{ref}:instance.env"], instance_repo).stdout
    for line in text.splitlines():
        if line.startswith("OSE_INSTANCE_PATHS="):
            return json.loads(line.split("=", 1)[1])
    return []


def clean_env(worktree: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSE_")}
    env["PYTHONPATH"] = str(worktree / "src")
    return env


def evaluate(worktree: Path, tag: str, tmp: Path) -> tuple[dict[str, str], dict[str, float]]:
    for name in EVAL_DATA:
        target = REPO_ROOT / "data" / name
        if target.exists():
            (worktree / "data" / name).symlink_to(target)
    if (REPO_ROOT / ".env").exists():
        (worktree / ".env").write_text((REPO_ROOT / ".env").read_text())
    env = clean_env(worktree)
    junit = tmp / f"{tag}.xml"
    run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--ignore=tests/eval",
         "--ignore=tests/answer", f"--junitxml={junit}"], worktree, check=False, env=env)
    report = run([sys.executable, "-m", "eval.run", "--index", "hybrid"], worktree, check=False, env=env)
    return load_junit(junit), parse_eval_report(report.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instance-repo", type=Path, required=True)
    parser.add_argument("--instance-ref", required=True, help="e.g. instance/sensalis")
    args = parser.parse_args(argv)
    instance_repo = args.instance_repo.resolve()

    run(["git", "fetch", "-q", "origin"], REPO_ROOT)
    main_sha = run(["git", "rev-parse", "origin/main"], REPO_ROOT).stdout.strip()
    run(["git", "fetch", "-q", "origin"], instance_repo)
    base = run(["git", "merge-base", args.instance_ref, main_sha], instance_repo).stdout.strip()
    changed = [p for p in run(["git", "diff", "--name-only", base, args.instance_ref], instance_repo).stdout.splitlines() if p]
    shared = shared_paths(changed, instance_paths_at(instance_repo, args.instance_ref))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {"instance_repo": str(instance_repo), "instance_ref": args.instance_ref, "main": main_sha,
              "merge_base": base, "shared_paths": shared, "checked_at": stamp}

    if not shared:
        report["verdict"] = "NOTHING_TO_PROMOTE"
        print(json.dumps(report, indent=2))
        return 0

    patch = run(["git", "diff", "--binary", base, args.instance_ref, "--", *shared], instance_repo).stdout
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        baseline_wt, candidate_wt = tmp / "baseline", tmp / "candidate"
        run(["git", "worktree", "add", "-q", "--detach", str(baseline_wt), main_sha], REPO_ROOT)
        run(["git", "worktree", "add", "-q", "--detach", str(candidate_wt), main_sha], REPO_ROOT)
        try:
            patch_file = tmp / "promote.patch"
            patch_file.write_text(patch)
            applied = run(["git", "apply", "--index", str(patch_file)], candidate_wt, check=False)
            if applied.returncode != 0:
                report.update(verdict="DOES_NOT_APPLY", detail=applied.stderr.strip())
                print(json.dumps(report, indent=2))
                return 3

            # Sequential on purpose: both suites share the Memgraph/Postgres test instances.
            base_tests, base_metrics = evaluate(baseline_wt, "baseline", tmp)
            cand_tests, cand_metrics = evaluate(candidate_wt, "candidate", tmp)
        finally:
            for wt in (baseline_wt, candidate_wt):
                run(["git", "worktree", "remove", "--force", str(wt)], REPO_ROOT, check=False)

    delta = compare_tests(base_tests, cand_tests)
    verdict = decide_promotion(delta, base_metrics, cand_metrics)
    report.update(verdict=verdict.verdict, reasons=verdict.reasons, baseline_metrics=base_metrics,
                  candidate_metrics=cand_metrics, tests=delta.__dict__)
    report_path = LOG_DIR / f"promote_check_{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2))
    if verdict.verdict == "PROMOTE":
        patch_out = LOG_DIR / f"promote_{stamp}.patch"
        patch_out.write_text(patch)
        report["patch"] = str(patch_out)
        report["apply_with"] = f"git apply --index {shlex.quote(str(patch_out))}  # in a checkout that can push main"
    print(json.dumps(report, indent=2))
    return 0 if verdict.verdict == "PROMOTE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
