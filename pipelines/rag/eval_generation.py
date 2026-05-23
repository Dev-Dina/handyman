"""Deterministic, CI-safe RAG generation-quality eval (no LLM judge, no network).

Builds the extractive answer (``build_extractive_answer`` over TF-IDF-retrieved
chunks — the deployed retrieval path) for each golden question and scores it with
explainable token-overlap proxies against the retrieved context and the
hand-written ``ideal_answer``.

These are *proxies*, not a semantic LLM judge. They are reproducible and require
no API key. An optional LLM-as-judge remains future/manual work.

Usage:
    python -m pipelines.rag.eval_generation            # 5 hand-labeled rows
    python -m pipelines.rag.eval_generation --all       # all golden rows
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.rag.config import (
    RAG_GENERATION_EVAL_CSV_PATH,
    RAG_GENERATION_EVAL_REPORT_PATH,
    RAG_GENERATION_JUDGE_CSV_PATH,
    RAG_GENERATION_JUDGE_REPORT_PATH,
    RAG_GOLDEN_PATH,
)
from app.services.rag.retrieval import build_extractive_answer, retrieve

# Deployed retrieval path: TF-IDF (alpha=0.0), no query transform, deterministic.
_EVAL_ALPHA = 0.0
_EVAL_TOP_K = 5
_MIN_TOKEN_LEN = 3

# Documented agreement thresholds (deterministic proxy vs LLM judge).
FAITHFULNESS_PROXY_THRESHOLD = 0.8
RELEVANCY_PROXY_THRESHOLD = 0.15  # extractive answers cover ~15% of ideal-answer tokens
_JUDGE_FAITHFUL_MIN = 4
_JUDGE_RELEVANT_MIN = 4

# Compact, explainable English stopword list (no external dependency).
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
        "had", "her", "was", "one", "our", "out", "has", "his", "how", "its",
        "may", "new", "now", "old", "see", "two", "way", "who", "did", "get",
        "use", "this", "that", "with", "from", "they", "have", "will", "your",
        "what", "when", "which", "their", "there", "would", "could", "should",
        "about", "into", "than", "then", "them", "these", "those", "such",
        "been", "were", "also", "only", "some", "more", "most", "other", "each",
        "does", "doing", "done", "very", "just", "like", "over", "under",
        "between", "because", "while", "where", "after", "before", "above",
        "below", "again", "once", "here", "both", "being", "having", "make",
        "made", "using", "used", "via", "per", "etc",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str | None) -> set[str]:
    """Lowercase, strip punctuation, drop short tokens and stopwords."""
    if not text:
        return set()
    return {
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) >= _MIN_TOKEN_LEN and tok not in _STOPWORDS
    }


def _recall(a: set[str], b: set[str]) -> float:
    """Fraction of tokens in ``a`` that also appear in ``b`` (|a∩b| / |a|)."""
    if not a:
        return 0.0
    return len(a & b) / len(a)


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def compute_row_metrics(answer: str | None, context: str, ideal: str | None) -> dict:
    """Deterministic token-overlap proxies for one (answer, context, ideal) triple."""
    a = tokenize(answer)
    c = tokenize(context)
    i = tokenize(ideal)
    unsupported = a - c
    unsupported_proxy = (len(unsupported) / len(a)) if a else 0.0
    return {
        "faithfulness_proxy": round(_recall(a, c), 4),
        "answer_relevancy_proxy": round(_recall(a, i), 4),
        "unsupported_claims_proxy": round(unsupported_proxy, 4),
        "unsupported_claims_count": len(unsupported),
        "retrieved_context_overlap": round(_jaccard(a, c), 4),
        "ideal_answer_overlap": round(_jaccard(a, i), 4),
        "answer_token_count": len(a),
    }


def _load_golden(path: Path, *, only_hand_labeled: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if only_hand_labeled and not row.get("hand_labeled_for_judge_check"):
                continue
            rows.append(row)
    return rows


async def _run(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        question = row["question"]
        ideal = row.get("ideal_answer")
        chunks, mode = await retrieve(
            question, top_k=_EVAL_TOP_K, alpha=_EVAL_ALPHA, query_transform="none"
        )
        answer = build_extractive_answer(chunks)
        context = "\n\n".join(c.get("text", "") for c in chunks)
        metrics = compute_row_metrics(answer, context, ideal)
        items.append(
            {
                "gold_id": row.get("golden_id", ""),
                "question": question,
                "ideal_answer": ideal,
                "answer": answer,
                "retrieved_chunk_ids": [c.get("chunk_id", "") for c in chunks],
                "ground_truth_chunk_ids": row.get("ground_truth_chunk_ids", []),
                "retrieval_mode": mode,
                **metrics,
            }
        )
    return items


def _mean(items: list[dict[str, Any]], key: str) -> float:
    if not items:
        return 0.0
    return round(sum(it[key] for it in items) / len(items), 4)


def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    cols = [
        "gold_id",
        "retrieval_mode",
        "faithfulness_proxy",
        "answer_relevancy_proxy",
        "unsupported_claims_proxy",
        "unsupported_claims_count",
        "retrieved_context_overlap",
        "ideal_answer_overlap",
        "answer_token_count",
        "question",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for it in items:
            writer.writerow(it)


def build_report(items: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    return {
        "eval_name": "rag_generation_deterministic_proxy",
        "mode": "deterministic_proxy",
        "judge": "none",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "golden_path": str(RAG_GOLDEN_PATH),
        "scope": scope,
        "retrieval_path": "tfidf_fallback (alpha=0.0, query_transform=none)",
        "rows_evaluated": len(items),
        "faithfulness_proxy_mean": _mean(items, "faithfulness_proxy"),
        "answer_relevancy_proxy_mean": _mean(items, "answer_relevancy_proxy"),
        "unsupported_claims_proxy_mean": _mean(items, "unsupported_claims_proxy"),
        "retrieved_context_overlap_mean": _mean(items, "retrieved_context_overlap"),
        "ideal_answer_overlap_mean": _mean(items, "ideal_answer_overlap"),
        "items": items,
        "limitations": [
            "Deterministic token-overlap proxy, not a semantic LLM judge.",
            "Answer is the extractive concatenation of retrieved chunks "
            "(build_extractive_answer), so faithfulness is high by construction.",
            "Scored on the deployed TF-IDF retrieval path; not E5 hybrid.",
            "CI-safe and reproducible; no API key or network required.",
            "Optional LLM-as-judge (faithfulness/answer-relevancy) remains "
            "future/manual work.",
        ],
    }


# ── Optional LLM-as-judge (manual, Vault-gated; never run in CI) ──────────────

_JUDGE_SYSTEM_PROMPT = (
    "You are a strict evaluator of RAG answers. Judge only from the provided "
    "retrieved context and ideal answer. Respond with a single JSON object and "
    "nothing else."
)


def _judge_user_prompt(item: dict[str, Any]) -> str:
    chunks = "\n---\n".join(
        str(c) for c in item.get("retrieved_chunk_ids", [])
    )
    return (
        "Question:\n"
        f"{item.get('question', '')}\n\n"
        "Ideal answer:\n"
        f"{item.get('ideal_answer', '')}\n\n"
        "Generated (extractive) answer:\n"
        f"{item.get('answer', '')}\n\n"
        "Retrieved chunk ids:\n"
        f"{chunks}\n\n"
        "Return JSON only with keys: faithfulness_score (1-5), "
        "answer_relevancy_score (1-5), grounded (bool), "
        "directly_answers_question (bool), unsupported_claims (list of strings), "
        "rationale (short string)."
    )


def parse_judge_json(content: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response (tolerates code fences/prose)."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {
            "faithfulness_score": 0,
            "answer_relevancy_score": 0,
            "grounded": False,
            "directly_answers_question": False,
            "unsupported_claims": [],
            "rationale": "unparseable judge response",
            "parse_error": True,
        }
    return data


def build_judge_report(
    items: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    *,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    """Pure aggregation of judge verdicts + agreement with the deterministic proxy."""
    judged: list[dict[str, Any]] = []
    for item, verdict in zip(items, verdicts, strict=True):
        det_faithful = item["faithfulness_proxy"] >= FAITHFULNESS_PROXY_THRESHOLD
        det_relevant = item["answer_relevancy_proxy"] >= RELEVANCY_PROXY_THRESHOLD
        judge_faithful = float(verdict.get("faithfulness_score", 0)) >= _JUDGE_FAITHFUL_MIN
        judge_relevant = (
            float(verdict.get("answer_relevancy_score", 0)) >= _JUDGE_RELEVANT_MIN
        )
        judged.append(
            {
                "gold_id": item.get("gold_id", ""),
                "question": item.get("question", ""),
                "faithfulness_proxy": item["faithfulness_proxy"],
                "answer_relevancy_proxy": item["answer_relevancy_proxy"],
                "faithfulness_score": verdict.get("faithfulness_score"),
                "answer_relevancy_score": verdict.get("answer_relevancy_score"),
                "grounded": verdict.get("grounded"),
                "directly_answers_question": verdict.get("directly_answers_question"),
                "unsupported_claims": verdict.get("unsupported_claims", []),
                "rationale": verdict.get("rationale", ""),
                "deterministic_faithful": det_faithful,
                "judge_faithful": judge_faithful,
                "faithfulness_agreement": det_faithful == judge_faithful,
                "deterministic_relevant": det_relevant,
                "judge_relevant": judge_relevant,
                "relevancy_agreement": det_relevant == judge_relevant,
            }
        )
    n = len(judged)

    def _rate(key: str) -> float:
        return round(sum(1 for j in judged if j[key]) / n, 4) if n else 0.0

    def _mean_score(key: str) -> float:
        vals = [float(j[key]) for j in judged if j[key] is not None]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    return {
        "eval_name": "rag_generation_llm_judge",
        "judge": "groq",
        "judge_model": model,
        "judge_temperature": temperature,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows_judged": n,
        "faithfulness_proxy_threshold": FAITHFULNESS_PROXY_THRESHOLD,
        "relevancy_proxy_threshold": RELEVANCY_PROXY_THRESHOLD,
        "judge_faithfulness_mean": _mean_score("faithfulness_score"),
        "judge_answer_relevancy_mean": _mean_score("answer_relevancy_score"),
        "faithfulness_agreement_rate": _rate("faithfulness_agreement"),
        "relevancy_agreement_rate": _rate("relevancy_agreement"),
        "items": judged,
        "limitations": [
            "LLM-as-judge is non-deterministic and depends on the judge model.",
            "Run manually only; never in CI. Requires a Groq key in Vault.",
            "Agreement compares judge verdicts to the deterministic token-overlap proxy.",
        ],
    }


def _load_groq_api_key() -> str:
    import os

    from app.infra.vault_client import VaultClient

    vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.getenv("VAULT_DEV_ROOT_TOKEN", "")
    vc = VaultClient(addr=vault_addr, token=vault_token)
    return vc.get_secret_from_path("llm", "groq_api_key")


async def _run_groq_judge(
    items: list[dict[str, Any]], model: str, temperature: float
) -> list[dict[str, Any]]:
    from app.infra.groq_client import GroqClient

    api_key = _load_groq_api_key()  # raises clearly if missing; never printed
    client = GroqClient(api_key=api_key)
    verdicts: list[dict[str, Any]] = []
    for item in items:
        choice = await client.chat(
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": _judge_user_prompt(item)},
            ],
            model=model,
            temperature=temperature,
        )
        content = (choice.get("message", {}) or {}).get("content", "")
        verdicts.append(parse_judge_json(content))
    return verdicts


def _write_judge_csv(path: Path, judged: list[dict[str, Any]]) -> None:
    cols = [
        "gold_id",
        "faithfulness_proxy",
        "faithfulness_score",
        "faithfulness_agreement",
        "answer_relevancy_proxy",
        "answer_relevancy_score",
        "relevancy_agreement",
        "grounded",
        "directly_answers_question",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in judged:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic CI-safe RAG generation eval (no LLM judge by default)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all golden rows (default: only hand_labeled_for_judge_check).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=RAG_GENERATION_EVAL_REPORT_PATH,
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=RAG_GENERATION_EVAL_CSV_PATH,
        help="Output CSV report path.",
    )
    parser.add_argument(
        "--judge",
        choices=["none", "groq"],
        default="none",
        help="Optional LLM-as-judge. 'none' (default) = deterministic proxy only. "
        "'groq' requires a Groq key in Vault and is manual/never-CI.",
    )
    parser.add_argument(
        "--judge-model",
        default="llama-3.3-70b-versatile",
        help="Judge model id (when --judge groq).",
    )
    parser.add_argument(
        "--judge-temperature", type=float, default=0.0, help="Judge sampling temperature."
    )
    parser.add_argument(
        "--judge-output",
        type=Path,
        default=RAG_GENERATION_JUDGE_REPORT_PATH,
        help="Output path for the LLM-judge report.",
    )
    args = parser.parse_args()

    if not RAG_GOLDEN_PATH.exists():
        raise FileNotFoundError(f"golden set not found: {RAG_GOLDEN_PATH}")

    only_hand_labeled = not args.all
    rows = _load_golden(RAG_GOLDEN_PATH, only_hand_labeled=only_hand_labeled)
    items = asyncio.run(_run(rows))
    report = build_report(
        items, scope="hand_labeled" if only_hand_labeled else "all"
    )

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_csv(args.csv_path, items)

    print(
        f"rows={report['rows_evaluated']} "
        f"faithfulness={report['faithfulness_proxy_mean']:.4f} "
        f"answer_relevancy={report['answer_relevancy_proxy_mean']:.4f} "
        f"unsupported={report['unsupported_claims_proxy_mean']:.4f} "
        f"ideal_overlap={report['ideal_answer_overlap_mean']:.4f}"
    )
    print(f"Report: {args.report_path}")
    print(f"CSV:    {args.csv_path}")

    if args.judge == "groq":
        verdicts = asyncio.run(
            _run_groq_judge(items, args.judge_model, args.judge_temperature)
        )
        judge_report = build_judge_report(
            items, verdicts, model=args.judge_model, temperature=args.judge_temperature
        )
        args.judge_output.parent.mkdir(parents=True, exist_ok=True)
        args.judge_output.write_text(
            json.dumps(judge_report, indent=2) + "\n", encoding="utf-8"
        )
        _write_judge_csv(RAG_GENERATION_JUDGE_CSV_PATH, judge_report["items"])
        print(
            f"judge rows={judge_report['rows_judged']} "
            f"faithfulness_agreement={judge_report['faithfulness_agreement_rate']:.4f} "
            f"relevancy_agreement={judge_report['relevancy_agreement_rate']:.4f}"
        )
        print(f"Judge report: {args.judge_output}")


if __name__ == "__main__":
    main()
