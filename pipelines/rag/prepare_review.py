"""RAG-3: Prepare review-friendly candidate file for RAG golden set curation.

Reads rag_golden_candidates.csv and adds:
  answer_preview   - single-line max-300-char preview of ideal_answer (noise stripped)
  suggested_keep   - yes / maybe / no based on deterministic content analysis
  suggested_reason - brief human-readable explanation for the suggestion
  selected_for_final - empty; curator fills this in
  reviewer_notes   - empty; curator fills this in

Does NOT call LLMs, create embeddings, run retrieval, or fetch data.
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.services.rag.config import (  # noqa: E402
    RAG_GOLDEN_CANDIDATES_PATH,
    RAG_GOLDEN_DIR,
    RAG_GOLDEN_REVIEW_CSV_PATH,
    RAG_GOLDEN_REVIEW_SUMMARY_PATH,
)

_ANSWER_PREVIEW_MAX = 300

# ---------------------------------------------------------------------------
# Per-candidate review analysis (deterministic, no external services)
# ---------------------------------------------------------------------------
_ANALYSIS: dict[str, tuple[str, str]] = {
    "cand_0000": (
        "maybe",
        "clear docs answer but has markdown badge and image tag noise to clean",
    ),
    "cand_0001": (
        "maybe",
        "clear docs answer but has Hugo shortcode template noise to clean",
    ),
    "cand_0002": ("yes", "clear docs answer about DNS namespace behavior"),
    "cand_0003": ("yes", "clear docs answer about Service abstraction"),
    "cand_0004": ("yes", "clear docs answer about volume persistence rationale"),
    "cand_0005": ("yes", "clear docs answer about Deployment use cases"),
    "cand_0006": (
        "maybe",
        "clear docs answer but has Hugo shortcode and note template noise to clean",
    ),
    "cand_0007": ("yes", "clear how-to answer for cluster node debugging"),
    "cand_0008": (
        "yes",
        "clear issue/problem answer about privilege escalation via nodes/proxy",
    ),
    "cand_0009": (
        "yes",
        "clear issue/problem answer about devicemanager multi-plugin behavior",
    ),
    "cand_0010": (
        "yes",
        "clear issue/problem answer about webhook context deadline bug",
    ),
    "cand_0011": (
        "no",
        "answer is a raw metric label string with no explanation of why",
    ),
    "cand_0012": ("maybe", "vague feature request with unclear problem scope"),
    "cand_0013": (
        "yes",
        "clear issue/problem answer about apiserver_response_sizes gap for CRDs",
    ),
    "cand_0014": (
        "maybe",
        "clear issue description but answer contains raw kubelet state file dump",
    ),
    "cand_0015": (
        "yes",
        "clear issue/problem answer about MilliValue integer overflow bug",
    ),
    "cand_0016": (
        "maybe",
        "too vague - single-sentence feature request with no technical detail",
    ),
    "cand_0017": (
        "yes",
        "clear issue/problem answer about Deployment Recreate strategy stall",
    ),
    "cand_0018": (
        "no",
        "too vague - internal refactoring request about CEL cost location",
    ),
    "cand_0019": (
        "yes",
        "clear issue/problem answer about CPU limit rounding bug in v1.32",
    ),
    "cand_0020": (
        "no",
        "answer is a GitHub URL and code snippet without explanatory text",
    ),
    "cand_0021": (
        "yes",
        "clear issue/problem answer about IPVS proxy RealServer weight logic",
    ),
    "cand_0022": (
        "yes",
        "clear issue/problem answer about default memory eviction threshold",
    ),
    "cand_0023": (
        "maybe",
        "clear data race issue but answer includes raw integration test output",
    ),
    "cand_0024": (
        "no",
        "too vague - answer only references another PR with no substantive content",
    ),
    "cand_0025": (
        "yes",
        "clear issue/problem answer about EventTime population in client-go",
    ),
    "cand_0026": (
        "maybe",
        "clear bug description but answer is raw kubectl apply output with YAML",
    ),
    "cand_0027": (
        "no",
        "answer is a CI run log table with timestamps and no semantic content",
    ),
    "cand_0028": (
        "maybe",
        "useful maintainer guidance but answer is a single brief sentence",
    ),
    "cand_0029": ("yes", "useful maintainer guidance with API documentation reference"),
    "cand_0030": (
        "yes",
        "useful maintainer guidance explaining webhook timeout behavior",
    ),
    "cand_0031": (
        "yes",
        "useful maintainer guidance with clear overflow fix recommendation",
    ),
    "cand_0032": (
        "yes",
        "useful maintainer guidance with historical context and no-change decision",
    ),
    "cand_0033": (
        "yes",
        "useful maintainer guidance explaining NRI plugin and runc design constraints",
    ),
    "cand_0034": (
        "maybe",
        "useful maintainer guidance but answer includes raw kubectl output",
    ),
    "cand_0035": (
        "yes",
        "useful maintainer guidance from SIG Node meeting on kubelet configuration",
    ),
    "cand_0036": (
        "yes",
        "useful maintainer guidance with PR reference and atomic pointer design suggestion",
    ),
    "cand_0037": (
        "maybe",
        "useful maintainer guidance but more discussion prompt than resolution",
    ),
    "cand_0038": (
        "yes",
        "useful maintainer guidance recommending events/v1 API migration",
    ),
    "cand_0039": ("yes", "useful maintainer guidance confirming bug scope beyond SSA"),
    "cand_0040": ("no", "answer is a raw code diff patch with no explanatory text"),
    "cand_0041": (
        "yes",
        "useful maintainer guidance explaining CSI driver mount directory behavior",
    ),
    "cand_0042": ("no", "answer is a raw gRPC error log block with no explanation"),
}


def _make_answer_preview(ideal_answer: str) -> str:
    text = ideal_answer
    # Remove markdown image badges  (![](...) and <img ...>)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<img[^>]*/?>", "", text, flags=re.IGNORECASE)
    # Remove Hugo shortcodes  ({{< ... >}})
    text = re.sub(r"\{\{<[^>]*>\}\}", "", text)
    # Remove code fences
    text = re.sub(r"```\w*", "", text)
    # Collapse all whitespace to single space
    text = re.sub(r"\s+", " ", text).strip()
    # Strip markdown bold/italic markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Strip leading list bullet or heading
    text = re.sub(r"^[\-\*#]+\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _ANSWER_PREVIEW_MAX:
        cut = text[: _ANSWER_PREVIEW_MAX - 3]
        last_period = cut.rfind(". ")
        if last_period > 80:
            text = cut[: last_period + 1]
        else:
            text = cut + "..."
    return text


def main() -> None:
    with open(RAG_GOLDEN_CANDIDATES_PATH, encoding="utf-8", newline="") as f:
        original = list(csv.DictReader(f))

    new_cols = [
        "answer_preview",
        "suggested_keep",
        "suggested_reason",
        "selected_for_final",
        "reviewer_notes",
    ]
    fieldnames = list(original[0].keys()) + new_cols

    rows: list[dict] = []
    for row in original:
        cid = row["candidate_id"]
        suggested_keep, suggested_reason = _ANALYSIS.get(
            cid, ("yes", "no specific analysis — review manually")
        )
        new_row = dict(row)
        new_row["answer_preview"] = _make_answer_preview(row["ideal_answer"])
        new_row["suggested_keep"] = suggested_keep
        new_row["suggested_reason"] = suggested_reason
        new_row["selected_for_final"] = ""
        new_row["reviewer_notes"] = ""
        rows.append(new_row)

    RAG_GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAG_GOLDEN_REVIEW_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    yes_count = sum(1 for r in rows if r["suggested_keep"] == "yes")
    maybe_count = sum(1 for r in rows if r["suggested_keep"] == "maybe")
    no_count = sum(1 for r in rows if r["suggested_keep"] == "no")

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_candidates": len(rows),
        "suggested_keep_yes": yes_count,
        "suggested_keep_maybe": maybe_count,
        "suggested_keep_no": no_count,
        "review_csv": str(RAG_GOLDEN_REVIEW_CSV_PATH),
        "original_candidates_csv": str(RAG_GOLDEN_CANDIDATES_PATH),
        "new_columns": new_cols,
        "workflow": (
            "Curator reviews suggested_keep column. "
            "Set selected_for_final=yes for 25 rows, "
            "hand_labeled_for_judge_check=true for at least 5, "
            "then run pipelines/rag/finalize_golden.py."
        ),
    }
    with open(RAG_GOLDEN_REVIEW_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Generated {len(rows)} rows -> {RAG_GOLDEN_REVIEW_CSV_PATH}")
    print(f"  yes={yes_count}  maybe={maybe_count}  no={no_count}")
    print(f"Summary: {RAG_GOLDEN_REVIEW_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
