import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path
    import pandas as pd
    import matplotlib.pyplot as plt

    DATA_DIR = Path("data/processed")
    Path("reports") # noqa: E402
    Path("reports/official/figures")

    train_path = DATA_DIR / "train.csv"
    val_path = DATA_DIR / "val.csv"
    test_path = DATA_DIR / "test.csv"

    train_path, val_path, test_path
    return pd, plt, test_path, train_path, val_path


@app.cell
def _(pd, test_path, train_path, val_path):
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"

    df = pd.concat([train_df, val_df, test_df], ignore_index=True)

    df.shape, df.columns.tolist()
    return (df,)


@app.cell
def _(df):
    balance = (
        df.groupby(["split", "final_label"])
        .size()
        .unstack(fill_value=0)
        .reindex(["train", "val", "test"])
    )

    balance
    return (balance,)


@app.cell
def _(balance, plt):
    ax = balance.plot(kind="bar", figsize=(8, 4))
    ax.set_title("Official Split Class Balance")
    ax.set_xlabel("Split")
    ax.set_ylabel("Issue count")
    ax.legend(title="Label")
    plt.tight_layout()
    plt.gcf()
    return


@app.cell
def _(df):
    label = "question"  # change to bug, feature, docs, question

    sample = df[df["final_label"] == label][
        ["split", "issue_number", "title", "final_label", "raw_labels", "html_url"]
    ].sample(10, random_state=7)

    sample
    return


@app.cell
def _(df):
    df["title_len"] = df["title"].fillna("").str.len()
    df["body_len"] = df["body"].fillna("").str.len()
    df["total_text_len"] = df["title_len"] + df["body_len"]

    length_summary = df.groupby("final_label")["total_text_len"].describe().round(1)

    length_summary
    return


@app.cell
def _(df):
    df["title_len"] = df["title"].fillna("").str.len()
    df["body_len"] = df["body"].fillna("").str.len()
    df["total_text_len"] = df["title_len"] + df["body_len"]

    length_by_label = (
        df.groupby("final_label")["total_text_len"]
        .agg(
            avg_length="mean",
            median_length="median",
            max_length="max",
            min_length="min",
            count="count",
        )
        .round(1)
        .reset_index()
    )

    length_by_label
    return


app._unparsable_cell(
    r"""
        longest = (
        df.sort_values("total_text_len", ascending=False)
            [["split", "issue_number", "final_label", "title", "total_text_len", "html_url"]]
        .head(20)
    )

    longest
    """,
    name="_",
)


@app.cell
def _(df):
    def non_ascii_ratio(text: str) -> float:
        if not isinstance(text, str) or not text:
            return 0.0
        return sum(ord(ch) > 127 for ch in text) / len(text)

    df["non_ascii_ratio"] = (
        df["title"].fillna("") + " " + df["body"].fillna("")
    ).apply(non_ascii_ratio)

    non_ascii_summary = (
        df.groupby(["split", "final_label"])["non_ascii_ratio"]
        .agg(["mean", "max"])
        .round(4)
    )

    non_ascii_summary
    return


@app.cell
def _(df):
    non_ascii_rows = (
        df[df["non_ascii_ratio"] > 0.02]
        .sort_values("non_ascii_ratio", ascending=False)[
            [
                "split",
                "issue_number",
                "final_label",
                "title",
                "non_ascii_ratio",
                "raw_labels",
                "html_url",
            ]
        ]
        .head(30)
    )

    non_ascii_rows
    return


if __name__ == "__main__":
    app.run()
