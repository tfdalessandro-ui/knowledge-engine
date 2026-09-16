"""The research-to-production loop's daily driver. Two mechanical,
deliberately simple rules -- no LLM, no judgment call, both auditable in
one glance at the code:

1. DECIDE-AT-DAY-14: any candidate registered >= 14 days ago and still
   'pending' gets a mechanical decision -- benchmark_after >=
   benchmark_before -> promote; otherwise -> drop. No partial credit, no
   human override built in (a human can always intervene directly on the
   CandidateStore, but the automated path is this one rule).
2. ROLLING-5 ROLLBACK WATCH: after any promotion, if the live version's
   score falls below the average of the trailing 5 recorded version
   scores, revert to whichever of those 5 versions scored best.

`extract a technique from a paper` is NOT automated here -- reading a
paper and turning it into an actual code change is a real engineering
step, done by a person/agent once per candidate, same as Step 7's
chunking-parameter discovery was. What this loop automates is everything
AFTER that: versioning the decision, benchmarking against the P0 harness,
and the mechanical promote/drop/rollback lifecycle. Candidates are
registered via `CandidateStore.register()` (see
`register_first_candidate.py` for how Step 7's chunking discovery was
registered as candidate #1).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import get_settings  # noqa: E402
from research.candidates import CandidateStore, ROLLING_WINDOW_SIZE  # noqa: E402


def decide(benchmark_before: float, benchmark_after: float) -> str:
    """The mechanical day-14 rule, as a pure function so it's directly
    testable/demoable without needing 14 real days to pass first."""
    return "promoted" if benchmark_after >= benchmark_before else "dropped"


def run_decisions(store: CandidateStore) -> list[tuple[int, str]]:
    decisions = []
    for c in store.pending_past_decision_date():
        outcome = decide(c.benchmark_before, c.benchmark_after)
        now = datetime.now(timezone.utc).isoformat()
        store.set_status(c.candidate_id, outcome, promoted_at=now if outcome == "promoted" else None)
        if outcome == "promoted":
            store.record_version_score(c.candidate_id, c.benchmark_after)
        decisions.append((c.candidate_id, outcome))
    return decisions


def check_rollback(store: CandidateStore) -> str | None:
    window = store.trailing_window(ROLLING_WINDOW_SIZE)
    if len(window) < ROLLING_WINDOW_SIZE:
        return None
    current = window[0]
    trailing_avg = sum(window) / len(window)
    if current < trailing_avg:
        best = max(window)
        return f"ROLLBACK TRIGGERED: current version ({current:.4f}) fell below the trailing-{ROLLING_WINDOW_SIZE} average ({trailing_avg:.4f}); best of those 5 was {best:.4f} -- revert to it (manual config restore, see version_history)"
    return None


def main() -> int:
    settings = get_settings()
    store = CandidateStore(settings.research_candidates_db_path)

    decisions = run_decisions(store)
    rollback_msg = check_rollback(store)

    now = datetime.now(timezone.utc)
    if not decisions and not rollback_msg:
        print(f"{now.isoformat()}: no candidates due for a decision, no rollback triggered")
        return 0

    for candidate_id, outcome in decisions:
        print(f"candidate {candidate_id}: {outcome}")
    if rollback_msg:
        print(rollback_msg)

    log_path = Path(__file__).resolve().parents[1] / f"LOGBOOK_{now.strftime('%m%d%Y_%H%M%S')}.md"
    log_path.write_text(f"""# Logbook — research_loop.py decision run ({now.strftime('%Y-%m-%d %H:%M UTC')})

Automated day-14 decision check (`research/loop.py`, systemd `ose-research-loop.timer`).

## Decisions made this run
{chr(10).join(f'- candidate {cid}: **{outcome}**' for cid, outcome in decisions) if decisions else '- none due'}

## Rollback watch
{rollback_msg if rollback_msg else 'Not triggered (fewer than 5 recorded versions, or current version at/above the trailing-5 average).'}
""")
    print(f"Logged: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
