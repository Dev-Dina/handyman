"""
Create classification golden set candidates for hand curation.

Reads:
  data/raw/kubernetes_issues.jsonl
  data/processed/{train,val,test}.csv  (exclusion list)

Writes:
  evals/golden/classification_golden_candidates.csv

Selects CANDIDATES_PER_CLASS candidates per class (4 classes = 48 total).
gold_label and curator_notes are left blank for manual completion.
"""

from __future__ import annotations

import csv
import json
import re

from app.core.paths import EVALS_DIR, PROJECT_ROOT, RAW_DATA_DIR
from ml.classifier_config import (
    LABELS,
    OFFICIAL_TEST_PATH,
    OFFICIAL_TRAIN_PATH,
    OFFICIAL_VAL_PATH,
)

_RAW_JSONL = RAW_DATA_DIR / "kubernetes_issues.jsonl"
_OUT_CSV = EVALS_DIR / "golden" / "classification_golden_candidates.csv"

CANDIDATES_PER_CLASS = 12
_BODY_PREVIEW_CHARS = 1200

_LABEL_MAP: dict[str, str] = {
    "kind/bug": "bug",
    "kind/feature": "feature",
    "kind/documentation": "docs",
    "kind/support": "question",
}
_PRIORITY: dict[str, int] = {"bug": 0, "docs": 1, "feature": 2, "question": 3}

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@[A-Za-z0-9_\-]+")


def _body_preview(body: str) -> str:
    text = body.strip()
    text = _URL_RE.sub("<URL>", text)
    text = _MENTION_RE.sub("<USER>", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > _BODY_PREVIEW_CHARS:
        text = text[:_BODY_PREVIEW_CHARS].rstrip() + "…"
    return text


def _resolve_label(raw_labels: list[str]) -> tuple[str | None, bool]:
    """Return (suggested_label, is_conflict).

    is_conflict=True when more than one target label is present.
    Returns (None, False) if no target label found.
    """
    targets = [_LABEL_MAP[lbl] for lbl in raw_labels if lbl in _LABEL_MAP]
    if not targets:
        return None, False
    unique = sorted(set(targets), key=lambda t: _PRIORITY[t])
    return unique[0], len(unique) > 1


def _load_excluded_ids() -> set[int]:
    excluded: set[int] = set()
    for path in (
        OFFICIAL_TRAIN_PATH,
        OFFICIAL_VAL_PATH,
        OFFICIAL_TEST_PATH,
    ):
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                excluded.add(int(row["issue_number"]))
    return excluded


def _load_candidates(excluded: set[int]) -> dict[str, list[dict]]:
    pools: dict[str, list[dict]] = {lbl: [] for lbl in LABELS}

    with _RAW_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            num = int(rec["issue_number"])
            if num in excluded:
                continue

            body = (rec.get("body") or "").strip()
            if not body:
                continue

            raw_labels: list[str] = rec.get("raw_labels") or []
            suggested, is_conflict = _resolve_label(raw_labels)
            if suggested is None:
                continue

            pools[suggested].append(
                {
                    "issue_number": num,
                    "title": rec.get("title") or "",
                    "body_preview": _body_preview(body),
                    "raw_labels": "; ".join(raw_labels),
                    "suggested_label": suggested,
                    "is_conflict": is_conflict,
                    "gold_label": "",
                    "curator_notes": "",
                    "created_at": rec.get("created_at") or "",
                    "closed_at": rec.get("closed_at") or "",
                    "html_url": rec.get("html_url") or "",
                }
            )

    return pools


def _sample_evenly(candidates: list[dict], n: int) -> list[dict]:
    """Sample n items spread evenly across the sorted list (by created_at)."""
    candidates = sorted(candidates, key=lambda r: r["created_at"])
    if len(candidates) <= n:
        return candidates
    step = len(candidates) / n
    return [candidates[int(i * step)] for i in range(n)]


def _select(pools: dict[str, list[dict]]) -> list[dict]:
    selected: list[dict] = []
    for label in LABELS:
        pool = pools[label]
        # Prefer single-label issues for clarity of gold annotation
        single = [r for r in pool if not r["is_conflict"]]
        multi = [r for r in pool if r["is_conflict"]]

        if len(single) >= CANDIDATES_PER_CLASS:
            chosen = _sample_evenly(single, CANDIDATES_PER_CLASS)
        else:
            chosen = single + _sample_evenly(multi, CANDIDATES_PER_CLASS - len(single))

        for row in chosen:
            row.pop("is_conflict")
        selected.extend(chosen)

    return selected


_OUT_COLS = [
    "issue_number",
    "title",
    "body_preview",
    "raw_labels",
    "suggested_label",
    "gold_label",
    "curator_notes",
    "created_at",
    "closed_at",
    "html_url",
]


def main() -> None:
    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    print("loading exclusion list…")
    excluded = _load_excluded_ids()
    print(f"  excluded {len(excluded)} issue_numbers from official splits")

    print("scanning data/raw/kubernetes_issues.jsonl…")
    pools = _load_candidates(excluded)
    for lbl in LABELS:
        print(f"  {lbl}: {len(pools[lbl])} candidates available")

    rows = _select(pools)
    print(f"selected {len(rows)} candidates ({CANDIDATES_PER_CLASS} per class)")

    with _OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_OUT_COLS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {_OUT_CSV.relative_to(PROJECT_ROOT)}")
    print("next step: open the CSV and fill gold_label + curator_notes for 25 issues")


if __name__ == "__main__":
    main()
