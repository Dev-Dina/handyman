"""Evaluation Defense page — deployed-vs-offline truth, real metrics, honest gaps."""

from __future__ import annotations

import json

import streamlit as st

import chatbot.api_client as client
from chatbot.components import lifecycle_badge, page_proves
from chatbot.pages._shared import (
    GENERATION_EVAL_REPORT,
    RAG_API_EVAL_REPORT,
    render_classifier_metrics_table,
    render_rag_metrics_table,
)


def page_eval_defense() -> None:
    st.title("Evaluation Defense")
    page_proves(
        "The deployed-vs-offline truth — what is actually served, the real metrics, "
        "and the honest eval gaps."
    )
    st.caption(
        "Honest account of what is evaluated vs what is served. No metric here is "
        "invented; unimplemented evals are shown as gaps, not numbers."
    )

    gen_present = GENERATION_EVAL_REPORT.exists()
    bcol1, bcol2, bcol3, bcol4 = st.columns(4)
    bcol1.metric("Classifier", lifecycle_badge("deployed"), "LR TF-IDF")
    bcol2.metric("CodeBERT", lifecycle_badge("offline"), "primary by eval")
    bcol3.metric("RAG hybrid (E5)", lifecycle_badge("deployed"), "served via /embed")
    bcol4.metric(
        "Generation eval",
        lifecycle_badge("deployed" if gen_present else "gap"),
        "deterministic proxy" if gen_present else "not implemented",
    )

    with st.expander(
        "Live eval summary (served by the API — no chatbot rebuild needed)"
    ):
        summary = client.get_eval_summary()
        if "error" in summary:
            st.caption(f"API eval summary unavailable: {summary['error']}")
        else:
            rag_sum = summary.get("rag_retrieval", {})
            st.caption(
                f"hybrid artifact present: `{rag_sum.get('hybrid_artifact_present')}` · "
                f"offline E5 hybrid: hit@5=`{rag_sum.get('offline_best_e5_hybrid', {}).get('hit_at_5')}`"
            )
            st.json(summary)

    st.subheader("Served vs evaluated")
    st.markdown(
        "| Capability | Best by evaluation | Served at runtime (Docker) |\n"
        "|---|---|---|\n"
        "| Issue classifier | CodeBERT (macro-F1 0.7061) | **LogisticRegression TF-IDF** (GPU-free, CI-safe) |\n"
        "| RAG retrieval | E5 hybrid α=0.7 (hit@5 0.68) | **E5 hybrid served** via model_server /embed; TF-IDF fallback (hit@5 ≈ 0.40) |"
    )
    st.info(
        "CodeBERT is **primary by evaluation, not Docker-served** (it needs torch/GPU). "
        "**E5 hybrid retrieval is now served in Docker**: model_server exposes a CPU "
        "`/embed` endpoint (transformers, mean-pool + L2) and the E5 chunk embeddings ship "
        "in the API image (`artifacts/rag/`). Live `/api/v1/rag/query` returns "
        "`retriever_used=hybrid`; it falls back to TF-IDF if `/embed` or the artifact is "
        "unavailable. Torch lives only in the model_server image."
    )

    st.divider()
    st.subheader("Classifier metrics (official)")
    render_classifier_metrics_table()

    st.divider()
    st.subheader("RAG retrieval metrics")
    render_rag_metrics_table()
    st.caption(
        "Deployed runtime serves **E5 hybrid** (`retriever_used=hybrid`, verified live) "
        "when model_server `/embed` + the shipped E5 chunk embeddings are present; "
        "otherwise it transparently falls back to `tfidf_fallback`."
    )
    if RAG_API_EVAL_REPORT.exists():
        try:
            rep = json.loads(RAG_API_EVAL_REPORT.read_text())
            st.caption(
                f"Latest CI eval ({RAG_API_EVAL_REPORT}): "
                f"mode=`{rep.get('retrieval_mode', '?')}` · "
                f"hit@5=`{rep.get('hit_at_5', '?')}` · "
                f"mrr@10=`{rep.get('mrr_at_10', '?')}` · "
                f"n=`{rep.get('n_questions', '?')}`"
            )
        except Exception as exc:  # noqa: BLE001
            st.caption(f"Could not parse RAG eval report: {exc}")

    st.divider()
    st.subheader("Generation eval (faithfulness / answer relevancy)")
    gen = None
    if GENERATION_EVAL_REPORT.exists():
        try:
            gen = json.loads(GENERATION_EVAL_REPORT.read_text())
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Could not parse generation eval report: {exc}")
    if gen:
        st.caption(
            f"Deterministic CI-safe proxy ({lifecycle_badge('deployed')}) · "
            f"judge=`{gen.get('judge', 'none')}` · "
            f"rows={gen.get('rows_evaluated', '?')} · "
            f"scope=`{gen.get('scope', '?')}`"
        )
        g1, g2, g3 = st.columns(3)
        g1.metric("Faithfulness (proxy)", gen.get("faithfulness_proxy_mean", "—"))
        g2.metric(
            "Answer relevancy (proxy)", gen.get("answer_relevancy_proxy_mean", "—")
        )
        g3.metric(
            "Unsupported claims (proxy)", gen.get("unsupported_claims_proxy_mean", "—")
        )
        h1, h2 = st.columns(2)
        h1.metric(
            "Retrieved-context overlap", gen.get("retrieved_context_overlap_mean", "—")
        )
        h2.metric("Ideal-answer overlap", gen.get("ideal_answer_overlap_mean", "—"))
        with st.expander("Limitations of this proxy"):
            for lim in gen.get("limitations", []):
                st.markdown(f"- {lim}")
        with st.expander("Per-row detail"):
            st.json(gen.get("items", []))
    else:
        st.warning(
            f"{lifecycle_badge('gap')} **Generation eval report not found in this "
            "container.** Generate it with `python -m pipelines.rag.eval_generation` "
            "and rebuild the chatbot image. The golden set carries `ideal_answer` and "
            "`hand_labeled_for_judge_check` for a deterministic (token-overlap) proxy, "
            "with an opt-in LLM judge. Retrieval eval (hit@5 / mrr@10) above is gated in CI."
        )

    st.divider()
    st.subheader("How to defend this")
    st.markdown(
        "- **Deployment is a deliberate trade-off, not a shortcut.** CodeBERT wins on "
        "macro-F1 (0.7061) but needs GPU/torch; we serve LogisticRegression TF-IDF "
        "(0.6938) so the demo is GPU-free, fast, and CI-safe — a −0.012 macro-F1 cost.\n"
        "- **RAG serves E5 hybrid live, and is honest about it.** `retriever_used` reads "
        "`hybrid` when model_server `/embed` + the shipped E5 chunk embeddings are present "
        "(hit@5 0.68 offline-measured), and transparently falls back to `tfidf_fallback` "
        "otherwise — the field always reflects what actually ran.\n"
        "- **Metrics are reproducible.** `pipelines.classifier.eval_golden` and "
        "`pipelines.rag.eval_api` regenerate the gated numbers; thresholds live in "
        "`eval_thresholds.yaml`.\n"
        "- **Generation quality has a deterministic proxy.** Faithfulness / answer "
        "relevancy are scored by reproducible token-overlap over the 5 hand-labeled "
        "golden rows (`pipelines.rag.eval_generation`) — CI-safe, no API key. It is a "
        "proxy, not a semantic LLM judge; an LLM-as-judge remains optional/manual. We "
        "never fabricate scores."
    )
