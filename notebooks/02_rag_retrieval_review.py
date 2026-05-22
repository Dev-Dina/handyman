import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import json

    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd

    try:
        from app.core.paths import EVALS_DIR, REPORTS_DIR
    except ImportError:
        from pathlib import Path

        # Fallback for running the notebook outside the package import context.
        def discover_project_root(start: Path) -> Path:
            for candidate in (start, *start.parents):
                if (candidate / "pyproject.toml").is_file():
                    return candidate
            raise RuntimeError("Could not discover project root")

        PROJECT_ROOT = discover_project_root(Path.cwd().resolve())
        REPORTS_DIR = PROJECT_ROOT / "reports"
        EVALS_DIR = PROJECT_ROOT / "evals"

    def read_json(path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    return EVALS_DIR, REPORTS_DIR, mo, pd, plt, read_json


@app.cell
def _(mo):
    mo.md(
        """
        # Overview

        The RAG pipeline uses a leakage-checked corpus from Kubernetes issues,
        issue comments, and curated docs. The golden set has 25 examples with
        docs, issue, and comment coverage.
        """
    )
    return


@app.cell
def _(EVALS_DIR, REPORTS_DIR, pd, read_json):
    corpus = read_json(REPORTS_DIR / "rag" / "corpus_collection_report.json")
    leakage = read_json(REPORTS_DIR / "rag" / "leakage_report.json")
    golden = read_json(EVALS_DIR / "golden" / "rag" / "rag_golden_summary.json")
    overview = pd.DataFrame(
        [
            {"metric": "docs_collected", "value": corpus["docs_collected_count"]},
            {"metric": "issues_selected", "value": corpus["issues_selected_count"]},
            {
                "metric": "comments_collected",
                "value": corpus["total_comments_collected"],
            },
            {"metric": "leakage_passed", "value": leakage.get("leakage_passed")},
            {"metric": "golden_rows", "value": golden["row_count"]},
            {
                "metric": "hand_labeled_for_judge_check",
                "value": golden["hand_labeled_for_judge_check_count"],
            },
        ]
    )
    overview
    return corpus, golden, overview


@app.cell
def _(mo):
    mo.md("## Chunking decision")
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    chunking = read_json(REPORTS_DIR / "rag" / "chunking_report.json")
    chunk_rows = [
        {
            "strategy": "baseline_fixed",
            "chunks": chunking["baseline_chunk_count"],
            "dropped_tiny_chunks": chunking["baseline_dropped_tiny_chunks"],
            "avg_char_length": chunking["baseline_avg_char_length"],
        },
        {
            "strategy": "section_aware",
            "chunks": chunking["section_aware_chunk_count"],
            "dropped_tiny_chunks": chunking["section_aware_dropped_tiny_chunks"],
            "avg_char_length": chunking["section_aware_avg_char_length"],
        },
    ]
    chunking_table = pd.DataFrame(chunk_rows)
    chunking_table
    return chunking, chunking_table


@app.cell
def _(chunking_table, plt):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(chunking_table["strategy"], chunking_table["chunks"])
    ax.set_title("Chunk Counts By Strategy")
    ax.set_xlabel("Strategy")
    ax.set_ylabel("Chunk count")
    fig.tight_layout()
    fig
    return


@app.cell
def _(chunking, mo):
    mo.md(
        f"""
        Section-aware chunking was chosen because it preserves headings, issue
        template sections, and comment metadata. Chosen strategy:
        **{chunking["chosen_for_next_phase"]}**.
        """
    )
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    embedding = read_json(
        REPORTS_DIR / "rag" / "retrieval" / "embedding_model_comparison.json"
    )
    embedding_table = pd.DataFrame(embedding["models"]).sort_values("rank")
    embedding_table[["rank", "model", "hit_at_5", "mrr_at_10", "latency_seconds"]]
    return embedding, embedding_table


@app.cell
def _(embedding_table, mo):
    mo.vstack(
        [
            mo.md("## Embedding model comparison"),
            embedding_table[
                ["rank", "model", "hit_at_5", "mrr_at_10", "latency_seconds"]
            ],
        ]
    )
    return


@app.cell
def _(embedding_table, plt):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(embedding_table["model"], embedding_table["mrr_at_10"])
    ax.set_title("Embedding Comparison MRR@10")
    ax.set_xlabel("Model")
    ax.set_ylabel("MRR@10")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    hybrid = read_json(
        REPORTS_DIR / "rag" / "retrieval" / "hybrid_alpha_comparison.json"
    )
    hybrid_table = pd.DataFrame(hybrid["runs"]).sort_values("rank")
    hybrid_table[["rank", "model", "alpha", "hit_at_5", "mrr_at_10"]]
    return hybrid, hybrid_table


@app.cell
def _(hybrid_table, mo):
    mo.vstack(
        [
            mo.md("## Hybrid retrieval"),
            hybrid_table[["rank", "model", "alpha", "hit_at_5", "mrr_at_10"]],
        ]
    )
    return


@app.cell
def _(hybrid_table, plt):
    fig, ax = plt.subplots(figsize=(8, 4))
    for model, group in hybrid_table.groupby("model"):
        ordered = group.sort_values("alpha")
        ax.plot(ordered["alpha"], ordered["hit_at_5"], marker="o", label=model)
    ax.set_title("Hybrid Alpha Sweep Hit@5")
    ax.set_xlabel("Dense alpha")
    ax.set_ylabel("Hit@5")
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    fig
    return


@app.cell
def _(hybrid, mo):
    mo.md(
        f"""
        Final production retrieval decision: **{hybrid["best_model"]}** hybrid
        with alpha **{hybrid["best_alpha"]}**.
        """
    )
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    rerank = read_json(REPORTS_DIR / "rag" / "retrieval" / "rerank_comparison.json")
    rerank_table = pd.DataFrame(rerank["runs"]).sort_values("rank")
    rerank_table[["rank", "model", "hit_at_5", "mrr_at_10", "latency_seconds"]]
    return rerank_table


@app.cell
def _(mo, rerank_table):
    mo.vstack(
        [
            mo.md(
                """
                ## Reranker review

                The reranker was evaluated and rejected for the final E5
                pipeline because it reduced hit@5 and added complexity/latency
                relative to the selected hybrid run.
                """
            ),
            rerank_table[["rank", "model", "hit_at_5", "mrr_at_10", "latency_seconds"]],
        ]
    )
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    api_report_path = REPORTS_DIR / "rag" / "api_eval_report.json"
    if api_report_path.exists():
        api_report = read_json(api_report_path)
        ci_table = pd.DataFrame(
            [
                {
                    "mode": "CI TF-IDF baseline",
                    "hit_at_5": api_report["hit_at_5"],
                    "mrr_at_10": api_report["mrr_at_10"],
                    "retrieval_mode": api_report["retrieval_mode"],
                    "row_count": api_report["n_questions"],
                },
                {
                    "mode": "Production E5 hybrid",
                    "hit_at_5": 0.68,
                    "mrr_at_10": 0.3293,
                    "retrieval_mode": "hybrid",
                    "row_count": api_report["n_questions"],
                },
            ]
        )
    else:
        ci_table = pd.DataFrame()
    ci_table
    return (ci_table,)


@app.cell
def _(ci_table, mo):
    mo.vstack(
        [
            mo.md(
                """
                ## CI-safe vs production eval

                CI uses the deterministic TF-IDF baseline so it does not need
                E5, modelserver, GPU, Docker, or network access. Production
                uses E5 hybrid alpha=0.7, so CI thresholds are intentionally
                lower.
                """
            ),
            ci_table,
        ]
    )
    return


@app.cell
def _(pd):
    final_decisions = pd.DataFrame(
        [
            {
                "item": "E5 hybrid alpha=0.7",
                "decision": "used in production",
                "reason": "best overall hybrid hit@5/MRR@10",
            },
            {
                "item": "TF-IDF RAG eval",
                "decision": "used in CI",
                "reason": "deterministic and no external services",
            },
            {
                "item": "section-aware chunking",
                "decision": "used in production",
                "reason": "preserves semantic sections and metadata",
            },
            {
                "item": "cross-encoder reranker",
                "decision": "rejected / not used",
                "reason": "hurt E5 hit@5 and added complexity",
            },
            {
                "item": "MiniLM dense embeddings",
                "decision": "rejected / not used",
                "reason": "lower MRR@10 than E5",
            },
        ]
    )
    final_decisions
    return


if __name__ == "__main__":
    app.run()
