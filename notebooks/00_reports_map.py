import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():
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

    inventory_path = REPORTS_DIR / "report_inventory.csv"
    return PROJECT_ROOT, REPORTS_DIR, inventory_path, mo, pd, plt


@app.cell
def _(inventory_path, mo):
    mo.md(
        """
        # Overview

        This notebook maps the `reports/` directory into official reports,
        CI/eval gates, failed experiments, archives, caches, and unknown files.
        It reads the generated inventory only; it does not modify reports.
        """
    )
    return


@app.cell
def _(inventory_path, pd):
    inventory = pd.read_csv(inventory_path)
    inventory.head()
    return (inventory,)


@app.cell
def _(inventory, mo):
    mo.md(
        f"""
        ## Report status categories

        Inventory rows: **{len(inventory)}**
        """
    )
    return


@app.cell
def _(inventory):
    status_counts = (
        inventory.groupby("status")
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["status"])
    )
    status_counts
    return (status_counts,)


@app.cell
def _(plt, status_counts):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(status_counts["status"], status_counts["count"])
    ax.set_title("Reports By Status")
    ax.set_xlabel("Status")
    ax.set_ylabel("File count")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig
    return


@app.cell
def _(inventory):
    track_counts = (
        inventory.groupby("track")
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["track"])
    )
    track_counts
    return (track_counts,)


@app.cell
def _(plt, track_counts):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(track_counts["track"], track_counts["count"])
    ax.set_title("Reports By Track")
    ax.set_xlabel("Track")
    ax.set_ylabel("File count")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig
    return


@app.cell
def _(inventory, mo):
    official = inventory[inventory["status"] == "ACTIVE_OFFICIAL"].sort_values("path")
    mo.vstack(
        [mo.md("## Official reports"), official[["path", "track", "used_by", "notes"]]]
    )
    return


@app.cell
def _(inventory, mo):
    eval_reports = inventory[inventory["status"] == "ACTIVE_EVAL"].sort_values("path")
    mo.vstack(
        [
            mo.md("## CI/eval reports"),
            eval_reports[["path", "track", "used_by", "notes"]],
        ]
    )
    return


@app.cell
def _(inventory, mo):
    failed = inventory[inventory["status"] == "FAILED_EXPERIMENT"].sort_values("path")
    mo.vstack(
        [
            mo.md("## Failed experiments"),
            failed[["path", "category", "used_by", "notes"]],
        ]
    )
    return


@app.cell
def _(inventory, mo):
    archive_cache = inventory[
        inventory["status"].isin(["ARCHIVE", "CACHE"])
    ].sort_values(["status", "path"])
    mo.vstack(
        [
            mo.md("## Archives and caches"),
            archive_cache[["path", "status", "track", "notes"]],
        ]
    )
    return


@app.cell
def _(inventory, mo):
    mo.md("## Unknown files / needs review")
    unknown = inventory[inventory["status"] == "UNKNOWN"].sort_values("path")
    if unknown.empty:
        result = mo.md("No unknown report files are currently classified.")
    else:
        result = unknown[["path", "extension", "size_bytes", "notes"]]
    result
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Final takeaway

        The team should use official reports for presentation/model decisions,
        CI/eval reports for deterministic gates, and failed experiment reports
        only as evidence explaining rejected paths. Archives and caches are kept
        for traceability, not as current sources of truth.
        """
    )
    return


if __name__ == "__main__":
    app.run()
