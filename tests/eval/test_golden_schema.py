"""Eval tests: golden-set schema and quality gates for classification_golden_curated.csv."""

from __future__ import annotations

import csv

import pytest

from app.core.paths import EVALS_DIR

pytestmark = pytest.mark.eval

_GOLDEN_CSV = EVALS_DIR / "golden" / "classification_golden_curated.csv"

_REQUIRED_COLUMNS = {"issue_number", "title", "gold_label", "curator_notes"}
_VALID_LABELS = {"bug", "feature", "docs", "question"}
_MIN_ROWS = 20


def _load_rows() -> list[dict]:
    with open(_GOLDEN_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_golden_csv_exists():
    assert _GOLDEN_CSV.exists(), f"Missing golden CSV: {_GOLDEN_CSV}"


def test_golden_csv_has_required_columns():
    with open(_GOLDEN_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = set(reader.fieldnames or [])
    missing = _REQUIRED_COLUMNS - cols
    assert not missing, f"Missing columns: {missing}"


def test_golden_csv_minimum_row_count():
    rows = _load_rows()
    assert len(rows) >= _MIN_ROWS, f"Expected >= {_MIN_ROWS} rows, got {len(rows)}"


def test_gold_labels_are_valid():
    rows = _load_rows()
    invalid = [
        (r.get("issue_number"), r.get("gold_label"))
        for r in rows
        if r.get("gold_label") not in _VALID_LABELS
    ]
    assert not invalid, f"Rows with invalid gold_label: {invalid}"


def test_gold_labels_not_empty():
    rows = _load_rows()
    empty = [r.get("issue_number") for r in rows if not r.get("gold_label", "").strip()]
    assert not empty, f"Rows missing gold_label: {empty}"


def test_curator_notes_not_empty():
    rows = _load_rows()
    empty = [
        r.get("issue_number") for r in rows if not r.get("curator_notes", "").strip()
    ]
    assert not empty, f"Rows with empty curator_notes: {empty}"


def test_issue_numbers_unique():
    rows = _load_rows()
    ids = [r.get("issue_number") for r in rows]
    assert len(ids) == len(set(ids)), "Duplicate issue_number entries found"


def test_all_four_labels_represented():
    rows = _load_rows()
    found = {r.get("gold_label") for r in rows}
    missing = _VALID_LABELS - found
    assert not missing, f"Labels not represented in golden set: {missing}"
