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
        from app.core.paths import PROJECT_ROOT, REPORTS_DIR
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

    def read_json(path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    return PROJECT_ROOT, REPORTS_DIR, mo, pd, plt, read_json


@app.cell
def _(mo):
    mo.md(
        """
        # Overview

        Classifier work used the `kubernetes/kubernetes` issue dataset with
        locked labels: `bug`, `feature`, `docs`, and `question`.

        The official dataset is `data/processed/` and remains locked. The final
        deployment decision is CodeBERT primary with LogisticRegression TF-IDF
        as the operational fallback.
        """
    )
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    comparison_path = REPORTS_DIR / "classifier_three_way_comparison.json"
    comparison = read_json(comparison_path)
    model_rows = []
    for key, model in comparison["models"].items():
        model_rows.append(
            {
                "track": key,
                "model": model["model"],
                "accuracy": model["accuracy"],
                "macro_f1": model["macro_f1"],
                "question_f1": model["per_class_f1"].get("question"),
                "avg_latency_seconds": model["avg_latency_seconds"],
                "deployment": model["deployment"],
            }
        )
    model_comparison = pd.DataFrame(model_rows).sort_values("macro_f1", ascending=False)
    model_comparison
    return comparison, model_comparison


@app.cell
def _(model_comparison, mo):
    mo.vstack([mo.md("## Official model comparison"), model_comparison])
    return


@app.cell
def _(model_comparison, plt):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(model_comparison["track"], model_comparison["macro_f1"])
    ax.set_title("Official Test Macro-F1")
    ax.set_xlabel("Track")
    ax.set_ylabel("Macro-F1")
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig
    return


@app.cell
def _(REPORTS_DIR, pd, read_json):
    experiments = []
    official_eval = read_json(REPORTS_DIR / "classical" / "best_classical_eval.json")
    experiments.append(
        {
            "experiment": "official_logistic_regression",
            "status": "official fallback",
            "accuracy": official_eval["test_results"]["accuracy"],
            "macro_f1": official_eval["test_results"]["macro_f1"],
            "question_f1": official_eval["test_results"][
                "per_class_precision_recall_f1"
            ]["question"]["f1"],
            "path": "reports/classical/best_classical_eval.json",
        }
    )
    failed_paths = {
        "support_question_augmentation": REPORTS_DIR
        / "experiments"
        / "failed"
        / "support_augmented"
        / "best_classical_eval.json",
        "cleaned_splits": REPORTS_DIR
        / "experiments"
        / "failed"
        / "cleaned_splits"
        / "classical_cleaned"
        / "best_classical_eval.json",
        "strict_text_preprocessing": REPORTS_DIR
        / "experiments"
        / "failed"
        / "strict_text"
        / "classical_strict"
        / "best_classical_eval.json",
    }
    for name, path in failed_paths.items():
        if path.exists():
            item = read_json(path)
            test = item["test_results"]
            experiments.append(
                {
                    "experiment": name,
                    "status": "rejected / archived",
                    "accuracy": test["accuracy"],
                    "macro_f1": test["macro_f1"],
                    "question_f1": test["per_class_precision_recall_f1"]["question"][
                        "f1"
                    ],
                    "path": path.relative_to(REPORTS_DIR.parent).as_posix(),
                }
            )
    experiment_inventory = pd.DataFrame(experiments)
    experiment_inventory
    return experiment_inventory, official_eval


@app.cell
def _(experiment_inventory, mo):
    mo.vstack([mo.md("## Experiment inventory"), experiment_inventory])
    return


@app.cell
def _(experiment_inventory, plt):
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(experiment_inventory["experiment"], experiment_inventory["macro_f1"])
    ax.set_title("Official And Failed Experiment Macro-F1")
    ax.set_xlabel("Experiment")
    ax.set_ylabel("Macro-F1")
    ax.set_ylim(0, 1)
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Failed experiment review

        Support/question augmentation, cleaned splits, and strict text
        preprocessing are preserved as evidence under
        `reports/experiments/failed/`. They are not used for training or
        deployment.

        The support augmentation run is the most nuanced result: some behavior
        improved, but macro-F1 and question-class balance were worse than the
        official fallback, so it stayed rejected.
        """
    )
    return


@app.cell
def _(REPORTS_DIR, pd):
    official_cm_path = REPORTS_DIR / "classical" / "confusion_matrix.csv"
    augmented_cm_path = (
        REPORTS_DIR
        / "experiments"
        / "failed"
        / "support_augmented"
        / "confusion_matrix.csv"
    )
    official_cm = pd.read_csv(official_cm_path, index_col=0)
    augmented_cm = pd.read_csv(augmented_cm_path, index_col=0)
    official_cm
    return augmented_cm, official_cm


@app.cell
def _(mo):
    mo.md("## Confusion matrices")
    return


@app.cell
def _(official_cm, plt):
    fig, ax = plt.subplots(figsize=(5, 4))
    image = ax.imshow(official_cm.values)
    ax.set_title("Official LR Confusion Matrix")
    ax.set_xticks(range(len(official_cm.columns)), official_cm.columns, rotation=45)
    ax.set_yticks(range(len(official_cm.index)), official_cm.index)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    for row_index, row in enumerate(official_cm.values):
        for col_index, value in enumerate(row):
            ax.text(col_index, row_index, int(value), ha="center", va="center")
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig
    return


@app.cell
def _(augmented_cm, plt):
    fig, ax = plt.subplots(figsize=(5, 4))
    image = ax.imshow(augmented_cm.values)
    ax.set_title("Support-Augmented Confusion Matrix")
    ax.set_xticks(range(len(augmented_cm.columns)), augmented_cm.columns, rotation=45)
    ax.set_yticks(range(len(augmented_cm.index)), augmented_cm.index)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    for row_index, row in enumerate(augmented_cm.values):
        for col_index, value in enumerate(row):
            ax.text(col_index, row_index, int(value), ha="center", va="center")
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig
    return


@app.cell
def _(augmented_cm, official_cm, pd):
    prediction_distribution = pd.DataFrame(
        {
            "true_official": official_cm.sum(axis=1),
            "predicted_official": official_cm.sum(axis=0),
            "true_augmented": augmented_cm.sum(axis=1),
            "predicted_augmented": augmented_cm.sum(axis=0),
        }
    ).fillna(0)
    prediction_distribution["predicted_delta_augmented_minus_official"] = (
        prediction_distribution["predicted_augmented"]
        - prediction_distribution["predicted_official"]
    )
    prediction_distribution
    return (prediction_distribution,)


@app.cell
def _(mo):
    mo.md(
        """
        ## Prediction distribution

        Confusion matrices let us inspect whether a run improved only by
        shifting predictions toward easier classes. In the augmentation run,
        the project specifically checks for bug overprediction and question
        underprediction instead of trusting accuracy alone.
        """
    )
    return


@app.cell
def _(plt, prediction_distribution):
    fig, ax = plt.subplots(figsize=(7, 4))
    prediction_distribution[["predicted_official", "predicted_augmented"]].plot(
        kind="bar", ax=ax
    )
    ax.set_title("Predicted Label Distribution")
    ax.set_xlabel("Label")
    ax.set_ylabel("Predicted count")
    fig.tight_layout()
    fig
    return


@app.cell
def _(REPORTS_DIR, official_eval, pd, read_json):
    official_per_class = {
        label: values["f1"]
        for label, values in official_eval["test_results"][
            "per_class_precision_recall_f1"
        ].items()
    }
    failed_eval = read_json(
        REPORTS_DIR
        / "experiments"
        / "failed"
        / "support_augmented"
        / "best_classical_eval.json"
    )
    augmented_per_class = {
        label: values["f1"]
        for label, values in failed_eval["test_results"][
            "per_class_precision_recall_f1"
        ].items()
    }
    per_class_delta = pd.DataFrame(
        {
            "official_f1": official_per_class,
            "support_augmented_f1": augmented_per_class,
        }
    )
    per_class_delta["delta"] = (
        per_class_delta["support_augmented_f1"] - per_class_delta["official_f1"]
    )
    per_class_delta
    return (per_class_delta,)


@app.cell
def _(mo, per_class_delta):
    mo.vstack([mo.md("## Per-class metric deltas"), per_class_delta])
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Decision rationale

        Accuracy alone was not enough. The selected classifier needed strong
        macro-F1 and acceptable per-class behavior across all four labels.
        Augmentation was rejected because it hurt class balance and question
        handling relative to the official fallback. CodeBERT remained primary
        because it had the best held-out macro-F1 and accuracy, while
        LogisticRegression remained the operational fallback because it is
        deterministic, fast, and requires no GPU.
        """
    )
    return


@app.cell
def _(pd):
    final_decisions = pd.DataFrame(
        [
            {
                "item": "CodeBERT",
                "decision": "officially used",
                "reason": "best held-out macro-F1 and accuracy",
            },
            {
                "item": "LogisticRegression TF-IDF",
                "decision": "officially used",
                "reason": "runtime fallback; no GPU required",
            },
            {
                "item": "Ollama llama3 baseline",
                "decision": "reference only",
                "reason": "lower macro-F1 and high latency",
            },
            {
                "item": "support/question augmentation",
                "decision": "rejected / archived",
                "reason": "macro-F1 and question behavior worse than fallback",
            },
            {
                "item": "cleaned splits",
                "decision": "rejected / archived",
                "reason": "no improvement over fallback",
            },
            {
                "item": "strict text preprocessing",
                "decision": "rejected / archived",
                "reason": "worse macro-F1",
            },
        ]
    )
    final_decisions
    return


if __name__ == "__main__":
    app.run()
