"""Tests for the deterministic RAG generation eval (no Groq, no Docker, no torch)."""

from __future__ import annotations

import json

import pytest

from pipelines.rag import eval_generation as ge

pytestmark = pytest.mark.eval


# ── tokenization ─────────────────────────────────────────────────────────────


def test_tokenize_lowercases_and_strips_punctuation():
    assert ge.tokenize("Pod CrashLoopBackOff!! (kubelet)") == {
        "pod",
        "crashloopbackoff",
        "kubelet",
    }


def test_tokenize_drops_stopwords_and_short_tokens():
    toks = ge.tokenize("the pod is in a CrashLoop state")
    assert "the" not in toks  # stopword
    assert "is" not in toks  # short
    assert "crashloop" in toks
    assert "state" in toks


def test_tokenize_empty_or_none():
    assert ge.tokenize("") == set()
    assert ge.tokenize(None) == set()


# ── metrics ──────────────────────────────────────────────────────────────────


def test_faithfulness_one_when_answer_subset_of_context():
    m = ge.compute_row_metrics(
        answer="kubelet restarts the failed container",
        context="the kubelet automatically restarts the failed container repeatedly",
        ideal="kubelet restarts containers",
    )
    assert m["faithfulness_proxy"] == 1.0
    assert m["unsupported_claims_proxy"] == 0.0
    assert m["unsupported_claims_count"] == 0


def test_unsupported_and_faithfulness_sum_to_one():
    m = ge.compute_row_metrics(
        answer="kubelet restarts dragons unicorns",
        context="kubelet restarts containers",
        ideal="kubelet behaviour",
    )
    assert round(m["faithfulness_proxy"] + m["unsupported_claims_proxy"], 4) == 1.0
    assert m["unsupported_claims_count"] >= 1


def test_empty_answer_yields_zero_proxies():
    m = ge.compute_row_metrics(answer=None, context="anything here", ideal="ideal")
    assert m["faithfulness_proxy"] == 0.0
    assert m["answer_relevancy_proxy"] == 0.0
    assert m["unsupported_claims_proxy"] == 0.0
    assert m["answer_token_count"] == 0


# ── golden loading ───────────────────────────────────────────────────────────


def test_load_golden_hand_labeled_default():
    rows = ge._load_golden(ge.RAG_GOLDEN_PATH, only_hand_labeled=True)
    assert len(rows) == 5
    assert all(r.get("hand_labeled_for_judge_check") for r in rows)


def test_load_golden_all_is_superset():
    hand = ge._load_golden(ge.RAG_GOLDEN_PATH, only_hand_labeled=True)
    all_rows = ge._load_golden(ge.RAG_GOLDEN_PATH, only_hand_labeled=False)
    assert len(all_rows) >= len(hand)
    assert len(all_rows) > 5


# ── report schema ────────────────────────────────────────────────────────────


def test_build_report_has_required_keys():
    items = [
        ge.compute_row_metrics("kubelet restarts", "kubelet restarts now", "kubelet")
        | {"gold_id": "g1", "question": "q", "retrieval_mode": "tfidf_fallback"}
    ]
    report = ge.build_report(items, scope="hand_labeled")
    for key in (
        "eval_name",
        "mode",
        "judge",
        "rows_evaluated",
        "faithfulness_proxy_mean",
        "answer_relevancy_proxy_mean",
        "unsupported_claims_proxy_mean",
        "retrieved_context_overlap_mean",
        "ideal_answer_overlap_mean",
        "items",
        "limitations",
    ):
        assert key in report, f"missing report key: {key}"
    assert report["judge"] == "none"
    assert report["rows_evaluated"] == 1
    assert isinstance(report["limitations"], list) and report["limitations"]


# ── end-to-end with stubbed retrieval (no corpus / no network) ────────────────


def test_main_writes_report_to_temp(tmp_path, monkeypatch):
    async def _fake_retrieve(question, *, top_k, alpha, query_transform):
        return (
            [
                {"chunk_id": "c1", "text": "kubelet restarts the failed container"},
                {"chunk_id": "c2", "text": "pods enter CrashLoopBackOff state"},
            ],
            "tfidf_fallback",
        )

    monkeypatch.setattr(ge, "retrieve", _fake_retrieve)
    monkeypatch.setattr(ge, "build_extractive_answer", lambda chunks: chunks[0]["text"])

    report_path = tmp_path / "gen.json"
    csv_path = tmp_path / "gen.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_generation",
            "--report-path",
            str(report_path),
            "--csv-path",
            str(csv_path),
        ],
    )

    ge.main()

    assert report_path.exists()
    assert csv_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["rows_evaluated"] == 5
    assert report["mode"] == "deterministic_proxy"
    assert 0.0 <= report["faithfulness_proxy_mean"] <= 1.0


# ── LLM-as-judge (fake judge — no Groq, no network) ──────────────────────────


def test_parse_judge_json_plain():
    d = ge.parse_judge_json('{"faithfulness_score": 5, "answer_relevancy_score": 4}')
    assert d["faithfulness_score"] == 5
    assert d["answer_relevancy_score"] == 4


def test_parse_judge_json_code_fenced_and_prose():
    content = (
        'Here is my verdict:\n```json\n{"faithfulness_score": 4, "grounded": true}\n```'
    )
    d = ge.parse_judge_json(content)
    assert d["faithfulness_score"] == 4
    assert d["grounded"] is True


def test_parse_judge_json_unparseable_returns_defaults():
    d = ge.parse_judge_json("not json at all")
    assert d["parse_error"] is True
    assert d["faithfulness_score"] == 0


def test_build_judge_report_agreement_fields():
    items = [
        {
            "gold_id": "g1",
            "question": "q1",
            "faithfulness_proxy": 1.0,
            "answer_relevancy_proxy": 0.2,
        },
        {
            "gold_id": "g2",
            "question": "q2",
            "faithfulness_proxy": 0.5,
            "answer_relevancy_proxy": 0.05,
        },
    ]
    verdicts = [
        {"faithfulness_score": 5, "answer_relevancy_score": 4, "grounded": True},
        {"faithfulness_score": 2, "answer_relevancy_score": 2, "grounded": False},
    ]
    rep = ge.build_judge_report(items, verdicts, model="fake", temperature=0.0)
    assert rep["judge"] == "groq"
    assert rep["rows_judged"] == 2
    # row1: proxy faithful (1.0>=0.8) AND judge faithful (5>=4) -> agree
    assert rep["items"][0]["faithfulness_agreement"] is True
    # row1: proxy relevant (0.2>=0.15) AND judge relevant (4>=4) -> agree
    assert rep["items"][0]["relevancy_agreement"] is True
    # row2: proxy not faithful (0.5<0.8) AND judge not faithful (2<4) -> agree (both False)
    assert rep["items"][1]["faithfulness_agreement"] is True
    assert rep["faithfulness_agreement_rate"] == 1.0
    assert rep["judge_faithfulness_mean"] == 3.5


def test_build_judge_report_disagreement():
    items = [
        {
            "gold_id": "g",
            "question": "q",
            "faithfulness_proxy": 1.0,
            "answer_relevancy_proxy": 0.2,
        }
    ]
    verdicts = [{"faithfulness_score": 1, "answer_relevancy_score": 1}]
    rep = ge.build_judge_report(items, verdicts, model="fake", temperature=0.0)
    # proxy faithful True, judge faithful False -> disagree
    assert rep["items"][0]["faithfulness_agreement"] is False
    assert rep["faithfulness_agreement_rate"] == 0.0
