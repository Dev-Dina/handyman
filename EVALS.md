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
uv run python -m pipelines.rag.eval_generation
uv run pytest -m unit -q
uv run pytest -m smoke -q
uv run pytest -m integration -q
uv run pytest -m eval -q
uv run pytest tests/build -q
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

**Live hybrid (Docker, manual):** with the stack up, hybrid retrieval is served end-to-end.
Verify against the running API (returns `retriever_used=hybrid`):

```bash
# model_server embedding endpoint
curl -s -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"texts":["query: what are kubernetes services"]}'

# live hybrid retrieval through the API
curl -s -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What does the Kubernetes documentation say about Services?","retriever":"hybrid","top_k":5}'
```

CI retrieval stays TF-IDF-only (`alpha=0.0`, no modelserver) — thresholds unchanged.

## RAG generation eval (deterministic proxy)

Script:
- `pipelines/rag/eval_generation.py`

Inputs:
- `evals/golden/rag/rag_golden.jsonl` (default: the 5 `hand_labeled_for_judge_check` rows; `--all` for every row)
- `data/rag/chunks/chunks_section_aware.jsonl`
- the deployed extractive answer (`build_extractive_answer` over TF-IDF-retrieved chunks)

Output:
- `reports/rag/generation_eval_report.json`, `reports/rag/generation_eval_report.csv`

Generation quality is evaluated with a deterministic CI-safe proxy over the 5 hand-labeled
RAG golden rows. It reports `faithfulness_proxy` and `answer_relevancy_proxy` (plus
`unsupported_claims_proxy`, `retrieved_context_overlap`, `ideal_answer_overlap`) using
explainable token-overlap after stopword filtering. **This is not a full semantic LLM judge;
an optional LLM-as-judge remains future/manual work.** No Groq, no API key, no network.

Current proxy result (5 hand-labeled rows, deployed TF-IDF path):
- faithfulness_proxy_mean: 1.0000 (extractive answers are drawn from retrieved chunks)
- answer_relevancy_proxy_mean: 0.1516
- unsupported_claims_proxy_mean: 0.0000
- ideal_answer_overlap_mean: 0.1443

## Deployed vs offline (no overclaiming)

- **RAG:** The current Docker runtime serves **E5-small-v2 hybrid retrieval with alpha=0.7**
  when the E5 chunk-embedding artifact (`artifacts/rag/intfloat_e5_small_v2_chunks.npy`) and
  the model_server `/embed` endpoint are available. Live `/api/v1/rag/query` returns
  `retriever_used=hybrid`. **TF-IDF remains the deterministic fallback** (and the CI gate),
  used automatically if `/embed` or the artifact is unavailable. The UI reports
  `retriever_used` so the active path is always visible. Torch/transformers live only in the
  model_server image; the API image stays torch-free.
- **Classifier:** CodeBERT is primary by evaluation. LogisticRegression TF-IDF is the deployed
  runtime fallback because it is CPU-safe, Docker-safe, and CI-safe.
- **Generation eval:** deterministic proxy only (above); semantic LLM-as-judge is future/manual.

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
