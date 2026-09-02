"""Trains a LightGBM LambdaMART reranker over logged query-candidate
interactions -- P3's tech choice, CPU-native, no GPU.

DELIBERATELY GATED: the roadmap flags starting this before enough logged
signal exists as a named risk. `train_reranker` refuses to fit a model
against fewer than `min_interactions` logged selections (default from
config: the roadmap's stated 500-1,000 minimum) and returns a clear
"blocked" result instead -- it does not train a token/placeholder model on
too little data and call it done. As of P3's build, this repo's query log is
empty (no real usage exists yet), so this path has never actually run in
"trained" mode outside of a synthetic-data unit test -- see
tests/ltr/test_train.py, which lowers the threshold deliberately to prove
the LightGBM plumbing itself works, not to claim the exit criterion is met.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ltr.features import FEATURE_NAMES, rows_to_dataset
from ltr.query_log import QueryLog


@dataclass
class TrainResult:
    trained: bool
    interactions: int
    min_interactions: int
    reason: str | None = None
    model_path: Path | None = None


def train_reranker(
    query_log_db_path: Path,
    min_interactions: int,
    model_out_path: Path,
    num_boost_round: int = 100,
) -> TrainResult:
    with QueryLog(query_log_db_path) as log:
        interactions = log.count_interactions()
        if interactions < min_interactions:
            return TrainResult(
                trained=False,
                interactions=interactions,
                min_interactions=min_interactions,
                reason=(
                    f"blocked: {interactions}/{min_interactions} minimum logged interactions "
                    "-- not enough real usage signal to train a reranker yet"
                ),
            )

        rows = log.training_rows()

    import lightgbm as lgb

    X, y, group = rows_to_dataset(rows)
    ranker = lgb.LGBMRanker(objective="lambdarank", n_estimators=num_boost_round, verbosity=-1)
    ranker.fit(X, y, group=group, feature_name=FEATURE_NAMES)

    model_out_path.parent.mkdir(parents=True, exist_ok=True)
    ranker.booster_.save_model(str(model_out_path))

    return TrainResult(
        trained=True,
        interactions=interactions,
        min_interactions=min_interactions,
        model_path=model_out_path,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    parser = argparse.ArgumentParser(description="Train the P3 LTR reranker (gated on logged interaction volume)")
    args = parser.parse_args(argv)

    settings = get_settings()
    result = train_reranker(settings.query_log_db_path, settings.ltr_min_interactions, settings.ltr_model_path)

    if not result.trained:
        print(result.reason)
        return 1

    print(f"trained on {result.interactions} interactions -> {result.model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
