"""Weekly status re-check (TODO.md item 8): a smoke test for the exact
failure class that cost most of a session on 2026-09-14 -- things that
were verified once, silently regressed, and nobody re-checked. This does
NOT replace a real status check (it can't judge relevance quality or
read logbooks); it only catches the four concrete regressions already
seen once each:

  1. KG entity count silently dropping to 0 (production Memgraph cleared
     by something and never repopulated).
  2. sensalis-node's checkout drifting from origin/main (uncommitted
     node-side work, or the node falling behind) -- the repo/execution
     split's failure mode, now that it's a git clone instead of a tar
     ship, this is finally checkable.
  3. The judgment set silently shrinking (data/judgments/judgments.json
     losing rows between runs -- catches both accidental data loss and a
     stale/wrong file being restored over a grown one).
  4. The live API not actually answering a real query (not just /health,
     which only proves the process is alive).

Exit code 0 = all clear. Non-zero = at least one check failed, details
printed AND appended to STATUS_ALERTS.md at the repo root (append-only,
so a failure is visible even if nobody re-reads the cron log) --
git-committing that append is intentionally left to a human, not
automated, so a false alarm can't quietly rewrite history unsupervised.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / "status_recheck_state.json"
ALERTS_PATH = REPO_ROOT / "STATUS_ALERTS.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_kg_count(settings) -> tuple[bool, str]:
    try:
        from neo4j import GraphDatabase

        d = GraphDatabase.driver(settings.memgraph_uri, auth=None)
        with d.session() as s:
            n = s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
            r = s.run("MATCH (:Entity)-[rel]->(:Entity) RETURN count(rel) AS c").single()["c"]
        d.close()
        if n == 0:
            return False, f"KG entity count is 0 (relations={r}) -- see TODO.md item 5, this exact regression before"
        return True, f"KG entity nodes={n} relations={r}"
    except Exception as exc:  # noqa: BLE001
        return False, f"KG check errored (Memgraph unreachable?): {exc}"


def check_git_sync(settings) -> tuple[bool, str]:
    try:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                                 capture_output=True, text=True, timeout=15).stdout.strip()
        subprocess.run(["git", "fetch", "origin", "main"], cwd=REPO_ROOT,
                        capture_output=True, text=True, timeout=30)
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                capture_output=True, text=True, timeout=10).stdout.strip()
        remote = subprocess.run(["git", "rev-parse", "origin/main"], cwd=REPO_ROOT,
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        problems = []
        if status:
            problems.append(f"uncommitted changes present:\n{status}")
        if settings.instance_branch == "main":
            if local != remote:
                problems.append(f"local HEAD ({local[:8]}) != origin/main ({remote[:8]})")
            detail = f"clean, HEAD == origin/main ({local[:8]})"
        else:
            # An instance branch is in sync when it contains every origin/main
            # commit; its own instance-only commits on top are expected.
            contained = subprocess.run(["git", "merge-base", "--is-ancestor", remote, "HEAD"], cwd=REPO_ROOT,
                                        capture_output=True, timeout=10).returncode == 0
            if not contained:
                behind = subprocess.run(["git", "rev-list", "--count", f"HEAD..{remote}"], cwd=REPO_ROOT,
                                         capture_output=True, text=True, timeout=10).stdout.strip()
                problems.append(f"instance branch is {behind} commit(s) behind origin/main ({remote[:8]})")
            detail = f"clean, {settings.instance_branch} contains origin/main ({remote[:8]})"
        if problems:
            return False, "; ".join(problems)
        return True, detail
    except Exception as exc:  # noqa: BLE001
        return False, f"git check errored: {exc}"


def check_judgment_set() -> tuple[bool, str]:
    judgments_path = REPO_ROOT / "data" / "judgments" / "judgments.json"
    try:
        rows = json.loads(judgments_path.read_text(encoding="utf-8"))
        n_rows = len(rows)
        n_queries = len({r["query"] for r in rows})
    except Exception as exc:  # noqa: BLE001
        return False, f"judgments.json unreadable: {exc}"

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    last_rows = state.get("judgment_rows")
    state["judgment_rows"] = n_rows
    state["judgment_queries"] = n_queries
    state["last_checked"] = _now()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))

    if last_rows is not None and n_rows < last_rows:
        return False, f"judgment set SHRANK: {last_rows} -> {n_rows} rows ({n_queries} queries)"
    return True, f"{n_rows} rows / {n_queries} queries (was {last_rows})"


def check_live_api(settings) -> tuple[bool, str]:
    try:
        r = httpx.get(f"{settings.api_base_url}/search", params={"q": settings.smoke_query, "k": 1}, timeout=15.0)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        if not hits:
            return False, "live /search returned zero hits for a known-good query"
        return True, f"/search answered, top hit doc_id={hits[0]['doc_id']}"
    except Exception as exc:  # noqa: BLE001
        return False, f"live /search unreachable or errored: {exc}"


def main() -> int:
    settings = get_settings()
    checks = {
        "kg_count": check_kg_count(settings),
        "git_sync": check_git_sync(settings),
        "judgment_set": check_judgment_set(),
        "live_api": check_live_api(settings),
    }

    all_ok = True
    lines = [f"[status_recheck] {_now()}"]
    for name, (ok, detail) in checks.items():
        status = "OK" if ok else "FAIL"
        lines.append(f"  {status:4} {name}: {detail}")
        all_ok = all_ok and ok
    report = "\n".join(lines)
    print(report)

    if not all_ok:
        ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n## {_now()}\n```\n{report}\n```\n")
        print(f"\n[status_recheck] at least one check FAILED -- appended to {ALERTS_PATH}")
        return 1

    print("\n[status_recheck] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
