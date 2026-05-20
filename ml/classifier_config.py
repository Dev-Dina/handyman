"""
Centralized classifier constants for the Maintainer's Copilot project.

All scripts that deal with classification labels, official paths, known metrics,
or LLM/Ollama defaults should import from here instead of hardcoding values.
"""

from __future__ import annotations

from pathlib import Path

# ── Labels ────────────────────────────────────────────────────────────────────

LABELS: tuple[str, ...] = ("bug", "feature", "docs", "question")

LABEL_DEFINITIONS: dict[str, str] = {
    "bug": "defect, regression, broken behavior, error, unexpected failure",
    "feature": "enhancement, new capability, behavior request, improvement",
    "docs": "documentation issue, missing or wrong docs, examples, website or docs content",
    "question": "support request, help, troubleshooting, user question about usage",
}

LABEL2ID: dict[str, int] = {lbl: i for i, lbl in enumerate(LABELS)}
ID2LABEL: dict[int, str] = {i: lbl for lbl, i in LABEL2ID.items()}

# ── Official dataset paths (LOCKED — do not replace) ─────────────────────────

OFFICIAL_TRAIN_PATH = Path("data/processed/train.csv")
OFFICIAL_VAL_PATH = Path("data/processed/val.csv")
OFFICIAL_TEST_PATH = Path("data/processed/test.csv")

# ── Official report directories ───────────────────────────────────────────────

OFFICIAL_CLASSICAL_REPORT_DIR = Path("reports/classical")
OFFICIAL_TRANSFORMER_REPORT_DIR = Path("reports/transformer")
OFFICIAL_LLM_REPORT_DIR = Path("reports/llm")
OFFICIAL_FIGURES_DIR = Path("reports/official/figures")

# ── Known official test-set metrics (update only after re-running eval) ───────

CLASSICAL_TEST_MACRO_F1: float = 0.693839  # LogisticRegression, TF-IDF
CODEBERT_TEST_MACRO_F1: float = 0.7061  # microsoft/codebert-base, 3 epochs

# ── Ollama / LLM baseline defaults ───────────────────────────────────────────

DEFAULT_OLLAMA_MODEL: str = "llama3:latest"
DEFAULT_OLLAMA_BASE_URL: str = "http://localhost:11434"
DEFAULT_LLM_MAX_CHARS: int = 6000
DEFAULT_LLM_TEMPERATURE: float = 0.0
DEFAULT_LLM_TIMEOUT_SECONDS: int = 120
