# Status Alerts

Append-only log of `scripts/status_recheck.py` failures (weekly cron,
`ose-status-recheck.timer`). Each entry is appended automatically by the
script when a check fails; **committing the append is a manual step**,
deliberately not automated, so a false alarm can't quietly rewrite
history unsupervised.

Empty means no recheck has ever failed since this file was created
(2026-09-14) -- it does not mean no check has ever run; see
`log/status_recheck.log` on sensalis-node for the full pass/fail history,
including clean runs.
