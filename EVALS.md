# Evaluation

## CI-safe evals

Normal CI is deterministic and does not require secrets, Docker runtime, GPU, Groq,
Ollama, live MinIO, or modelserver.

CI runs:

```bash
uv run ruff check app model_server ml pipelines tests chatbot
uv run python -m pipelines.classifier.eval_golden
uv run python -m pipelines.rag.eval_api
uv run pytest -q
```

CI also asserts that `torch` is not installed in the main environment.

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
