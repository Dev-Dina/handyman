# Reports Map

`reports/` contains project evidence, not training inputs. It includes official
classifier/RAG reports, CI eval outputs, failed experiment evidence, historical
archives, runtime summaries, and caches.

## Categories

| Status | Meaning |
|---|---|
| `ACTIVE_OFFICIAL` | Evidence used for final model/RAG decisions or presentation. |
| `ACTIVE_EVAL` | Deterministic CI/local eval gate output. |
| `ACTIVE_RUNTIME` | Runtime or indexing output used by tooling. |
| `FAILED_EXPERIMENT` | Rejected experiment evidence kept for auditability. |
| `ARCHIVE` | Historical outputs from earlier repo/dataset attempts. |
| `CACHE` | Intermediate or superseded output; not a decision source. |
| `UNKNOWN` | Needs review before use. |

The generated inventory is:

- `reports/report_inventory.csv`
- `reports/report_inventory.json`

Regenerate it with:

```powershell
.\.venv\Scripts\python.exe scripts/audit_reports.py
```

## Official Reports

Final presentation and locked decisions use:

- `reports/official/figures/`
- `reports/classifier_three_way_comparison.json`
- `reports/classifier_three_way_comparison.csv`
- `reports/classical/`
- `reports/transformer/`
- `reports/llm/llama3_full/`
- `reports/rag/chunking_report.json`
- `reports/rag/corpus_collection_report.json`
- `reports/rag/leakage_report.json`
- `reports/rag/retrieval/*comparison*`
- `reports/rag/retrieval/retrieval_runs_summary.csv`

## CI And Eval Reports

CI-safe eval gates use deterministic local paths only:

- `reports/classification_eval_report.json`
- `reports/rag/api_eval_report.json`
- `eval_thresholds.yaml`

Normal CI does not run Groq, Ollama, CodeBERT, E5 embedding generation, Docker,
GPU jobs, or live MinIO.

## Failed Experiments

Rejected experiments live under `reports/experiments/failed/`. They are retained
only as evidence for decisions:

- support/question augmentation
- cleaned splits
- strict text preprocessing

These reports explain why an experiment was rejected. They are not production
inputs.

## Archives And Caches

Archives live under `reports/archive/` and `reports/archive_numpy/`. Caches and
intermediate outputs include `reports/rag/embeddings_cache/`, non-final LLM
smoke runs, and superseded top-level transformer outputs.

## Naming Convention

Future reports should use stable, descriptive names:

- `<track>/<phase>_<purpose>.json` for structured summaries
- `<track>/<phase>_<purpose>.csv` for tabular outputs
- `<track>/retrieval/<run_name>.json|csv` for retrieval runs
- `official/figures/<number>_<title>.png` for presentation figures

## Warnings

- Do not delete failed or archived reports without an explicit cleanup task.
- Do not train from failed experiment data.
- `data/processed/` remains locked as the official classifier dataset.
