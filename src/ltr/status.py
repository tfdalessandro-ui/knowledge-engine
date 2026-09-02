"""Reports how much query-log signal has accumulated toward the LTR
training gate. Run: PYTHONPATH=src .venv/bin/python -m ltr.status
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings
from ltr.query_log import QueryLog


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    with QueryLog(settings.query_log_db_path) as log:
        queries = log.count_queries()
        interactions = log.count_interactions()

    threshold = settings.ltr_min_interactions
    eligible = interactions >= threshold
    print(f"queries logged      : {queries}")
    print(f"selections logged   : {interactions}")
    print(f"training threshold  : {threshold}")
    print(f"status              : {'ELIGIBLE' if eligible else 'BLOCKED'} "
          f"({interactions}/{threshold} interactions)")
    if not eligible:
        print(f"need {threshold - interactions} more logged selections before `ltr.train` will run for real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
