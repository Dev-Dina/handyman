# Evaluation

## Modular CI jobs

CI is split into independent jobs so each failure points to the exact layer.
A lint failure no longer masks a test failure; a missing asset no longer looks
like a Python crash.

| Job | Name in UI | Depends on | Purpose |
|---|---|---|---|
| `ci-assets` | CI assets | — | Checks gitignored assets exist before eval jobs run |
| `lint` | Lint | — | `ruff check` on all source + scripts + notebooks |
| `tests-unit` | Unit tests | — | `pytest -m unit` |
| `tests-smoke` | Smoke tests | — | `pytest -m smoke` |
| `tests-integration` | Integration tests | — | `pytest -m integration` |
| `tests-eval` | Eval schema tests | — | `pytest -m eval` |
| `tests-build` | Build/compose tests | — | `pytest -m build` |
| `classifier-golden-eval` | Classification golden eval | `ci-assets` | Runs LR TF-IDF eval on golden set |
| `rag-golden-eval` | RAG golden eval | `ci-assets` | Runs TF-IDF retrieval eval on golden set |
| `widget-build` | Widget build | — | `npm ci && npm run build` in `widget/` |
| `docker-compose-config` | Docker compose config | — | `docker compose config` only — no services started |

### Why `classifier-golden-eval` and `rag-golden-eval` depend on `ci-assets`

`artifacts/classical/best_model.joblib` and `data/rag/chunks/chunks_section_aware.jsonl`
are gitignored. On a fresh clone these files are absent. Without the asset gate, both eval
jobs fail with an obscure `FileNotFoundError` deep inside the pipeline — indistinguishable
from a code bug. With `ci-assets` as a dependency and `if: always()` on the eval jobs, GitHub
shows the asset check failed and the eval jobs fail explicitly (not silently
skip), giving a clear all-red signal instead of a partial-green CI.

The asset check script is `scripts/check_ci_assets.py`. It prints a per-file OK/MISS
status and exits 1 if anything is missing.

## CI-safe evals

Normal CI is deterministic and does not require secrets, Docker runtime, GPU, Groq,
Ollama, live MinIO, or modelserver.

Key commands that CI runs (via `uv sync --extra dev --extra ml --extra chatbot`):

```bash
uv run ruff check app model_server ml pipelines tests chatbot scripts notebooks
uv run python -m pipelines.classifier.eval_golden
uv run python -m pipelines.rag.eval_api
uv run pytest -m unit -q
uv run pytest -m smoke -q
uv run pytest -m integration -q
uv run pytest -m eval -q
uv run pytest -m build -q
```

Every Python job asserts that `torch` is not installed in the main environment.

## Classification golden eval

Script:
- `pipelines/classifier/eval_golden.py`

Inputs:
- `evals/golden/classification_golden.jsonl`
- `data/raw/kubernetes_issues.jsonl`
- `artifacts/classical/best_model.joblib`
- `eval_thresholds.yaml`

Output:
- `reports/classification_eval_report.json`

CI default model:
- `LogisticRegression TF-IDF`

Current CI-safe result:
- row_count: 25
- accuracy: 0.7200
- macro_f1: 0.6691
- threshold: `classification.macro_f1_min = 0.65`
- threshold_passed: true

CodeBERT and Ollama/Groq classifier baselines are not run in normal CI because they
require GPU/modelserver or live external/local LLM services. Their locked numbers remain
documented in `PROJECT_STATE.md`, `DECISIONS.md`, and classifier reports.

## RAG eval

Script:
- `pipelines/rag/eval_api.py`

Inputs:
- `evals/golden/rag/rag_golden.jsonl`
- `data/rag/chunks/chunks_section_aware.jsonl`
- `eval_thresholds.yaml`

Output:
- `reports/rag/api_eval_report.json`

CI default retrieval:
- TF-IDF only (`alpha=0.0`)
- no E5/modelserver required

Current CI-safe result:
- row_count: 25
- hit_at_5: 0.4000
- mrr_at_10: 0.1960
- thresholds: `rag.hit_at_5_min = 0.25`, `rag.mrr_at_10_min = 0.15`
- threshold_passed: true

Manual/non-CI retrieval experiments include E5 dense/hybrid and reranker sweeps. Those
are documented in `docs/RAG_TRACK_REPORT.md` and `reports/rag/retrieval/`.

## Why LLMs and neural models are not in normal CI

Normal CI avoids:
- Groq: requires secret and network.
- Ollama: requires local service and pulled model.
- CodeBERT/fine-tuning: requires Torch/GPU path and large model dependencies.
- E5 dense retrieval: requires modelserver or neural model runtime.

This keeps CI reproducible on a fresh GitHub runner.

## Thresholds

Thresholds live in `eval_thresholds.yaml` and must remain non-zero.

Current CI gates:
- `classification.macro_f1_min = 0.65`
- `rag.hit_at_5_min = 0.25`
- `rag.mrr_at_10_min = 0.15`
