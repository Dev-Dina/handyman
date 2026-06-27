"""Demo Runbook page — step-by-step walkthrough of the full system."""

from __future__ import annotations

import streamlit as st

from chatbot.components import page_proves
from chatbot.config import HOST_DEMO_URL, JAEGER_URL, MINIO_URL


def page_demo_runbook() -> None:
    st.title("Demo Runbook")
    page_proves(
        "The final walkthrough — exact steps to present the whole system end-to-end."
    )
    st.caption(
        "Step-by-step guide for a live presentation or walkthrough of the full system."
    )

    st.subheader("Prerequisites")
    st.code(
        "cp .env.example .env\n"
        "# Add your Groq key:\n"
        "docker compose up --build -d\n"
        'docker compose exec vault vault kv put secret/llm groq_api_key="gsk_your_key"',
        language="bash",
    )

    steps = [
        (
            "1. Verify all services healthy",
            "Open [System Health](?nav=System+Health) — API and model_server should show ✅.\n\n"
            "Or from terminal:\n"
            "```bash\n"
            "docker compose ps\n"
            "curl http://localhost:8000/healthz\n"
            "curl http://localhost:8001/healthz\n"
            "```",
        ),
        (
            "2. Register + login",
            "```bash\n"
            "curl -X POST http://localhost:8000/api/v1/auth/register \\\n"
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"email":"demo@example.com","password":"demo-password-123","role":"admin"}\'\n'
            "```\n"
            "Then login in this Streamlit app (left sidebar form).",
        ),
        (
            "3. Test RAG Explorer",
            "Go to **RAG Explorer**. Enter:\n"
            "- Question: `How do I configure a PodDisruptionBudget?`\n"
            "- Retriever: `hybrid`\n"
            "- Query transform: `technical_terms`\n\n"
            "Expected: extractive answer + ranked chunks with source_type and scores.",
        ),
        (
            "4. Test Classifier Playground",
            "Go to **Classifier Playground**. Enter:\n"
            "- Title: `Pod OOMKilled after node restart`\n"
            "- Body: `Steps to reproduce: upgrade node pool, pod gets OOMKilled`\n\n"
            "Expected: label=`bug`, confidence > 0.5, model=`lr_tfidf_fallback`.",
        ),
        (
            "5. Test Chat Copilot with tools",
            "Go to **Chat Copilot**. Enable tools: `rag_query`, `classify_issue`, `write_memory`.\n\n"
            "Send: `Classify this issue and find relevant docs: Pod OOMKilled after upgrade`\n\n"
            "Expected: LLM calls rag_query + classify_issue tools, returns structured answer, "
            "trace_id appears below response.",
        ),
        (
            "6. Check Memory Inspector",
            "Go to **Memory Inspector**. "
            "Short-term memory should show the messages from the previous chat. "
            "Long-term memory appears if write_memory was called.",
        ),
        (
            "7. Open Jaeger trace",
            f"Go to **Observability** — copy the last `trace_id`. "
            f"Open [{JAEGER_URL}]({JAEGER_URL}), select service `handyman`, "
            "paste the trace_id. See the full span waterfall.",
        ),
        (
            "8. Create a widget config (admin)",
            "Go to **Widget Manager** (admin required). "
            "Create a config with `allowed_origins: http://localhost:3000,http://localhost:8080`. "
            "Copy the `public_widget_id` from the result.",
        ),
        (
            "9. Open host demo widget",
            f"Open [{HOST_DEMO_URL}]({HOST_DEMO_URL}). "
            "A floating chat bubble should appear in the bottom-right corner. "
            "Click it — the widget expands. Send a message.\n\n"
            "If the bubble does not appear, update `demo/host/index.html` "
            "with the `public_widget_id` from step 8 and rebuild: "
            "`docker compose build host && docker compose up -d host`.",
        ),
        (
            "10. Check MinIO artifacts",
            f"Open [{MINIO_URL}]({MINIO_URL}) (minioadmin / minioadmin). "
            "Browse `handyman-artifacts` and `handyman-evals` buckets. "
            "Eval reports are uploaded by pipelines/rag/eval_api.py and the classifier eval pipeline.",
        ),
    ]

    for title, body in steps:
        with st.expander(title, expanded=False):
            st.markdown(body)

    st.divider()

    st.subheader("Official metrics summary")
    st.markdown(
        "| Track | Metric | Value |\n"
        "|---|---|---|\n"
        "| Classifier primary | CodeBERT macro-F1 | **0.7061** |\n"
        "| Classifier fallback | LR TF-IDF macro-F1 | **0.6938** |\n"
        "| Classifier baseline | Ollama llama3 macro-F1 | 0.5554 |\n"
        "| RAG (deployed) | E5 hybrid hit@5 | **0.68** |\n"
        "| RAG (deployed) | E5 hybrid MRR@10 | **0.329** |\n"
        "| RAG (CI baseline) | TF-IDF hit@5 | 0.40 |"
    )
