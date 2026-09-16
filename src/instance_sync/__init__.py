"""Keeps OSE instances (e.g. instance/sensalis) in sync with OSE main.

main -> instance: an instance branch is OSE main plus instance-owned paths only;
scripts/sync_instance.py merges main in and rolls back on any regression.
instance -> main: a shared-code change made on an instance is promoted only if
scripts/promote_check.py finds it non-regressive against the original instance.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ALWAYS_INSTANCE_OWNED = ("instance.env", "INSTANCE.md")


def is_instance_owned(path: str, instance_paths: list[str]) -> bool:
    for owned in (*ALWAYS_INSTANCE_OWNED, *instance_paths):
        owned = owned.rstrip("/")
        if path == owned or path.startswith(owned + "/"):
            return True
    return False


def shared_paths(changed: list[str], instance_paths: list[str]) -> list[str]:
    return sorted(p for p in changed if not is_instance_owned(p, instance_paths))


def load_junit(path: Path) -> dict[str, str]:
    outcomes = {}
    for tc in ET.parse(path).getroot().iter("testcase"):
        kind = "passed"
        for child in tc:
            if child.tag in ("failure", "error"):
                kind = "failed"
            elif child.tag == "skipped":
                kind = "skipped"
        outcomes[f"{tc.get('classname')}::{tc.get('name')}"] = kind
    return outcomes


@dataclass
class TestDelta:
    newly_failing: list[str] = field(default_factory=list)
    new_failing: list[str] = field(default_factory=list)
    vanished_passing: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    new_passing: list[str] = field(default_factory=list)

    @property
    def regressed(self) -> bool:
        return bool(self.newly_failing or self.new_failing)


def compare_tests(before: dict[str, str], after: dict[str, str]) -> TestDelta:
    return TestDelta(
        newly_failing=sorted(t for t, k in before.items() if k == "passed" and after.get(t) == "failed"),
        new_failing=sorted(t for t, k in after.items() if t not in before and k == "failed"),
        vanished_passing=sorted(t for t, k in before.items() if k == "passed" and t not in after),
        fixed=sorted(t for t, k in before.items() if k == "failed" and after.get(t) == "passed"),
        new_passing=sorted(t for t, k in after.items() if t not in before and k == "passed"),
    )


_METRIC_LINE = re.compile(r"^(nDCG@\d+|MRR|recall@\d+)\s*:\s*([0-9.]+)\s*$")


def parse_eval_report(text: str) -> dict[str, float]:
    metrics = {}
    for line in text.splitlines():
        m = _METRIC_LINE.match(line.strip())
        if m:
            metrics[m.group(1)] = float(m.group(2))
    return metrics


@dataclass
class PromotionVerdict:
    verdict: str  # PROMOTE | REJECT
    reasons: list[str]


def decide_promotion(tests: TestDelta, baseline: dict[str, float], candidate: dict[str, float],
                     primary_metric: str = "nDCG@10") -> PromotionVerdict:
    reasons = []
    if tests.newly_failing:
        reasons.append(f"tests newly failing: {tests.newly_failing}")
    if tests.new_failing:
        reasons.append(f"new tests failing: {tests.new_failing}")
    if primary_metric not in baseline or primary_metric not in candidate:
        reasons.append(f"{primary_metric} missing from eval output")
    elif candidate[primary_metric] < baseline[primary_metric]:
        reasons.append(f"{primary_metric} dropped {baseline[primary_metric]:.4f} -> {candidate[primary_metric]:.4f}")
    if reasons:
        return PromotionVerdict("REJECT", reasons)

    gains = []
    if candidate[primary_metric] > baseline[primary_metric]:
        gains.append(f"{primary_metric} {baseline[primary_metric]:.4f} -> {candidate[primary_metric]:.4f}")
    if tests.fixed:
        gains.append(f"fixes tests: {tests.fixed}")
    if tests.new_passing:
        gains.append(f"adds passing tests: {len(tests.new_passing)}")
    return PromotionVerdict("PROMOTE", gains or ["non-regressive (no metric or test change)"])
