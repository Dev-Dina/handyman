"""Eval threshold sanity checks."""

from __future__ import annotations

import yaml

from app.core.paths import PROJECT_ROOT

_THRESHOLDS_PATH = PROJECT_ROOT / "eval_thresholds.yaml"


def test_eval_thresholds_are_nonzero_and_sane() -> None:
    cfg = yaml.safe_load(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    values = (
        cfg["classification"]["macro_f1_min"],
        cfg["rag"]["hit_at_5_min"],
        cfg["rag"]["mrr_at_10_min"],
    )
    for value in values:
        assert 0.0 < value < 1.0
