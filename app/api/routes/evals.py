"""GET /api/v1/evals/summary — sanitized evaluation summary for the dashboard.

Lets the Streamlit Evaluation Defense page read eval results through the API
instead of baking report files into the chatbot image. Reads only small,
non-secret eval reports from the API filesystem; returns a flat summary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.paths import REPORTS_DIR
from app.services.rag.config import (
    HYBRID_ALPHA,
    RAG_API_EVAL_REPORT_PATH,
    RAG_CHUNK_EMBEDDINGS_PATH,
    RAG_GENERATION_EVAL_REPORT_PATH,
    RAG_GENERATION_JUDGE_REPORT_PATH,
)

router = APIRouter(prefix="/api/v1/evals", tags=["evals"])

_CLASSIFICATION_REPORT = REPORTS_DIR / "classification_eval_report.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return None


@router.get("/summary")
async def evals_summary() -> dict[str, Any]:
    clf = _read_json(_CLASSIFICATION_REPORT)
    rag = _read_json(RAG_API_EVAL_REPORT_PATH)
    gen = _read_json(RAG_GENERATION_EVAL_REPORT_PATH)
    judge = _read_json(RAG_GENERATION_JUDGE_REPORT_PATH)

    hybrid_artifact_present = RAG_CHUNK_EMBEDDINGS_PATH.exists()

    return {
        "classifier": {
            "served_model": "LogisticRegression TF-IDF",
            "primary_by_evaluation": "CodeBERT (not Docker-served, needs GPU)",
            "status": "deployed",
            "golden": None
            if not clf
            else {
                "accuracy": clf.get("accuracy"),
                "macro_f1": clf.get("macro_f1"),
                "threshold_passed": clf.get("threshold_passed"),
            },
        },
        "rag_retrieval": {
            "hybrid_alpha": HYBRID_ALPHA,
            "hybrid_artifact_present": hybrid_artifact_present,
            "offline_best_e5_hybrid": {
                "hit_at_5": 0.68,
                "mrr_at_10": 0.329,
                "alpha": 0.7,
            },
            "ci": None
            if not rag
            else {
                "mode": rag.get("retrieval_mode"),
                "hit_at_5": rag.get("hit_at_5"),
                "mrr_at_10": rag.get("mrr_at_10"),
                "n_questions": rag.get("n_questions"),
            },
            "note": "Live retriever_used is reported per query on /api/v1/rag/query.",
        },
        "generation_deterministic": {
            "status": "deployed" if gen else "gap",
            "report": None
            if not gen
            else {
                "rows_evaluated": gen.get("rows_evaluated"),
                "faithfulness_proxy_mean": gen.get("faithfulness_proxy_mean"),
                "answer_relevancy_proxy_mean": gen.get("answer_relevancy_proxy_mean"),
                "unsupported_claims_proxy_mean": gen.get(
                    "unsupported_claims_proxy_mean"
                ),
                "ideal_answer_overlap_mean": gen.get("ideal_answer_overlap_mean"),
            },
        },
        "generation_judge": {
            "status": "deployed" if judge else "gap",
            "report": None
            if not judge
            else {
                "rows_judged": judge.get("rows_judged"),
                "judge_model": judge.get("judge_model"),
                "judge_faithfulness_mean": judge.get("judge_faithfulness_mean"),
                "judge_answer_relevancy_mean": judge.get("judge_answer_relevancy_mean"),
                "faithfulness_agreement_rate": judge.get("faithfulness_agreement_rate"),
                "relevancy_agreement_rate": judge.get("relevancy_agreement_rate"),
            },
        },
    }
