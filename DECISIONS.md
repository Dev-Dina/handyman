# Decisions

## Dataset

**Chosen repo:** kubernetes/kubernetes

**Why:**
kubernetes/kubernetes is a large, actively maintained infrastructure project with
tens of thousands of closed issues. Maintainers apply structured `kind/*` labels
consistently, yielding clean signal for four target classes. The label set is
simple (4 target labels, exact match, no normalisation needed) and each class
has thousands of examples, giving a balanced supervised dataset.

## Label mapping

**Status:** CONFIRMED — LOCKED. EDA completed; dataset and splits finalized.

Final classes: bug / feature / docs / question

| GitHub label         | Project class |
|----------------------|---------------|
| kind/bug             | bug           |
| kind/feature         | feature       |
| kind/documentation   | docs          |
| kind/support         | question      |

Only issues carrying at least one of these four labels enter the supervised dataset.
Issues with none of these labels are dropped and recorded in EDA reports.

## Multi-label honesty policy

Multi-label issues are **not hidden** and **not silently dropped**.

1. Every issue's full GitHub label set is stored in `raw_labels` in the JSONL file.
2. For each issue, the set of *target* labels found is computed (e.g. kind/bug + kind/feature).
3. If exactly one target label is present → class assigned directly, no conflict.
4. If multiple target labels are present → deterministic conflict resolution is applied
   (see priority below) AND the issue is written to `reports/multilabel_conflicts.csv`
   with: issue_number, title, target_labels_found, chosen_final_label, resolution_reason, html_url.
5. The split report records: total conflict count, per-combination counts, examples,
   and the conflict policy string.

**Why transparency matters:**
Hiding conflicts (e.g. by only fetching with negative label filters) would undercount
real dataset ambiguity and make evaluation results misleading. Recording conflicts lets
us audit resolution quality and revisit the priority later.

## Conflict priority

bug > docs > feature > question

| Priority | Class       | Reason                                                              |
|----------|-------------|---------------------------------------------------------------------|
| 1        | bug         | Highest operational severity; a bug report is distinct              |
| 2        | docs        | Distinct assignment type; must not be swallowed by feature/support  |
| 3        | feature     | Product/change request; lower urgency than bugs or doc fixes        |
| 4        | question    | Weakest signal; support/usage questions are least actionable        |

## Fetching strategy

Uses GitHub Search API with per-class label queries:

    label:"kind/bug"           → up to 1000 closed issues
    label:"kind/feature"       → up to 1000 closed issues
    label:"kind/documentation" → up to 1000 closed issues
    label:"kind/support"       → up to 1000 closed issues

Issues appearing in multiple queries are deduplicated by issue_number.
GitHub always returns the full label set in the API response, so first-seen wins.
PRs are excluded by the `is:issue` Search API qualifier.
Negative label filters are NOT used — overlaps are preserved and reported.

## Split strategy

Time-based stratified split per class:
- Within each class, sort by created_at ascending.
- Oldest 70% → train, next 15% → val, newest 15% → test.
- Guarantees test is strictly newer than train within every class.
- Both global and per-class temporal order are validated and reported.
- Val/test fractions configurable via --val-frac / --test-frac flags.

**Note:** Final split will be run only after EDA confirms label distribution is acceptable.

**Temporal disclaimer:** A strict global chronological split caused the docs class to disappear from validation/test because all docs issues predate the global val/test cutoff. We therefore used per-class chronological stratification to preserve all four classes for macro-F1 and per-class F1 evaluation. Test examples are newer than train examples within each class, but not globally newer across all classes.

## Unlabeled / unmapped handling

Issues with no target label are:
- Excluded from the supervised train/val/test splits.
- Sampled and written to `reports/unlabeled_issues_sample.csv` for inspection.
- Counted in `reports/label_eda.json` under `unlabeled_count`.

## Classical model

Best model: LogisticRegression (TF-IDF).
val_macro_f1: 0.701875 — test_macro_f1: 0.693839.
Artifacts: artifacts/classical/best_model.*

## Support-only augmentation experiment (ablation — not adopted)

**What was tried:**
Fetched additional `kind/support` issues via `--supplement-label kind/support` to address the 405 issues lost to multi-label conflict resolution.
Resulted in `data/raw/kubernetes_issues_augmented.jsonl` (4 304 unique issues) and splits in `data/processed_augmented/`.

**Results:**

| Metric | Original split | Augmented split |
|---|---|---|
| Val macro-F1 | — | 0.840244 |
| Test macro-F1 | 0.693839 | 0.680766 |
| Question test F1 | — | 0.272727 |

**Decision: do not adopt.**
The augmented split improved validation macro-F1 but degraded test macro-F1 and left the question class weak (test F1 0.272727). The gap between val and test F1 (0.84 → 0.68) signals overfitting to the augmented distribution. The original balanced split (420/class train, 90/class val/test) remains the official classifier dataset.

**Official dataset:**
- `data/processed/train.csv` — 1 680 rows, 420/class
- `data/processed/val.csv` — 360 rows, 90/class
- `data/processed/test.csv` — 360 rows, 90/class

Augmented data and splits archived under `data/experiments/failed/support_augmented/` and `reports/experiments/failed/support_augmented/`.

## Classifier dataset — final decision (LOCKED)

**Official dataset:** `data/processed/` — 420/class train, 90/class val/test. Locked.

Three alternative preprocessing/data strategies were evaluated and rejected:

| Experiment | test_macro_f1 | vs baseline | Decision |
|---|---|---|---|
| Original (baseline) | 0.693839 | — | **OFFICIAL** |
| Support-only augmentation | 0.680766 | -0.013 | Rejected — val/test gap, weak question F1 |
| Cleaned splits (processed_cleaned) | 0.693839 | 0.000 | Rejected — no improvement |
| Strict text preprocessing | 0.637926 | -0.056 | Rejected — worse across all models |

**Ruling:** Original balanced split with default `model_text` preprocessing is the official classifier dataset. All experiments archived under `data/experiments/failed/` and `reports/experiments/failed/`.

Transformer and LLM baselines must use `data/processed/` only.

## Failed experiment archive locations

| Experiment | Data | Reports |
|---|---|---|
| Support-only augmentation | `data/experiments/failed/support_augmented/` | `reports/experiments/failed/support_augmented/` |
| Cleaned splits | `data/experiments/failed/cleaned_splits/` | `reports/experiments/failed/cleaned_splits/` |
| Strict text | `data/experiments/failed/strict_text/` | `reports/experiments/failed/strict_text/` |

Source scripts remain in `ml/` as documentation (do not delete).

## Fine-tuned transformer

**Chosen encoder:** microsoft/codebert-base  
**Run:** codebert_base_e3_len384 (3 epochs, batch 4, max_len 384, lr 2e-5)  
**Labels:** bug / docs / feature / question (same 4 classes, same IDs).

### Encoder comparison

| run_name | model | epochs | max_len | test_macro_f1 | question_f1 |
|---|---|---|---|---|---|
| bert-tiny | prajjwal1/bert-tiny | 3 | 128 | 0.5634 | 0.3624 |
| electra_small_e5_len384 | google/electra-small-discriminator | 5 | 384 | 0.6909 | 0.3922 |
| **codebert_base_e3_len384** | **microsoft/codebert-base** | **3** | **384** | **0.7061** | 0.2909 |
| minilm_l12_e5_len384 | microsoft/MiniLM-L12-H384-uncased | 5 | 384 | 0.6332 | **0.4510** |

**Why CodeBERT:** highest test macro-F1 among encoders and beats the classical baseline (+0.012). Pre-training on code-related corpora aligns with kubernetes issues (commands, YAML, logs, paths, versions).

**Note:** MiniLM has the best question_f1 (0.451) but is worst overall. Pending LLM baseline; final deployment choice deferred.

### Freeze policy

No frozen encoder layers. Full fine-tuning used.

- Training set has 1 680 balanced examples — not extremely small.
- Kubernetes issues contain domain-specific text: commands, YAML, logs, paths, versions, stack traces. Encoder adaptation was desirable.
- No measured overfitting: best_val_macro_f1=0.6971, test_macro_f1=0.7061 (gap +0.009).
- Partial freezing was not adopted because there was no overfitting signal requiring it.

## LLM baseline

**Model:** llama3:latest (Ollama local)  
**Approach:** Zero-shot classification via structured JSON prompt. No fine-tuning. No API key.  
**Run:** llama3_full — 360 test rows, temperature 0.0, max_chars 6000.

| Metric | Value |
|---|---|
| accuracy | 0.585 |
| macro_f1 | 0.5554 |
| question_f1 | 0.2385 |
| avg latency | 24.9 s/sample |
| total time | ~2.5 hours |

**Finding:** Zero-shot macro-F1 (0.555) is 0.139 below fine-tuned CodeBERT and 0.138 below classical TF-IDF baseline. The model over-predicts `bug` (recall 0.956, precision 0.432) and fails on `question` (F1 0.239). Despite zero cost and no training, zero-shot LLM is not competitive with even a simple TF-IDF classifier on this domain.

Artifacts: `reports/llm/llama3_full/`

## Deployment model choice

**Decision: FINAL**

| Track | Model | test_macro_f1 | test_accuracy | deployment |
|---|---|---|---|---|
| Classical | LogisticRegression (TF-IDF) | 0.6938 | 0.7139 | operational fallback |
| **Transformer** | **microsoft/codebert-base** | **0.7061** | **0.7500** | **PRIMARY** |
| LLM zero-shot | llama3:latest | 0.5554 | 0.5850 | not selected |

**Primary:** microsoft/codebert-base  
Artifact: `artifacts/transformer/codebert_base_e3_len384/`  
Rationale: Highest test macro-F1 and accuracy. Pre-training on code-related corpora fits kubernetes issues (YAML, commands, logs, paths, versions). Full fine-tune with no overfitting signal.

**Operational fallback:** LogisticRegression (TF-IDF)  
Artifact: `artifacts/classical/best_model.joblib`  
Rationale: Only 0.012 below CodeBERT on macro-F1. No GPU required. ~110 000× faster per-sample inference (0.22 ms vs 24.9 s/sample for Ollama; GPU inference for CodeBERT not measured but expected to be <10 ms). Useful if GPU is unavailable or latency budget is tight.

**LLM not selected:**  
Lowest macro-F1 (0.5554) and slowest inference (24.9 s/sample). Unsuitable for production classification at this accuracy level without few-shot examples or fine-tuning.

## Embedding model comparison

**Status:** DECIDED — all 3 candidate models evaluated on 25 golden examples, 2189 section-aware chunks.

| Rank | Model | hit@5 | recall@5 | mrr@10 | latency(s) | Status |
|---|---|---|---|---|---|---|
| 1 | intfloat/e5-small-v2 | **0.60** | **0.60** | **0.3307** | 170.1 | Evaluated — **CHOSEN** |
| 2 | BAAI/bge-small-en-v1.5 | 0.52 | 0.52 | 0.2815 | 175.9 | Evaluated |
| 3 | sentence-transformers/all-MiniLM-L6-v2 | 0.48 | 0.48 | 0.2091 | 20.6 | Evaluated |

**Chosen embedding model: intfloat/e5-small-v2**

Rationale: highest mrr@10 (0.3307, +5pp over BGE-small) and hit@5 (0.60, +8pp over BGE-small).
E5-small uses explicit `query:` / `passage:` prefixes during inference, enabling better asymmetric
retrieval (short question vs. longer passage). On Kubernetes domain queries this prefix-aware
encoding outperforms both BGE-small (retrieval-focused but symmetric) and MiniLM (similarity-focused).

Notable: E5 dense-only hit@5 (0.60) equals the BGE-small + hybrid + cross-encoder reranker pipeline,
with higher mrr@10 (0.3307 vs 0.3159), purely from the embedding quality.

**Note on hybrid/reranker experiments:** The hybrid alpha sweep and reranker ablations in RAG-5
used BAAI/bge-small-en-v1.5 (evaluated before e5 completed). Those results remain valid as
ablation evidence for pipeline design choices (they are not invalidated by the e5 finding).

## Chunking strategy

**Status:** DECIDED — section-aware (RAG-2, completed 2026-05-21).

| Strategy | chunks | avg_chars | mrr@10 implication |
|---|---|---|---|
| Fixed-size (512 chars) | 2596 | 435 | baseline |
| Section-aware (≤1024 chars) | 2189 | 458 | chosen — preserves semantic boundaries |

Section-aware chosen: markdown headers and paragraph boundaries produce more coherent chunks
than arbitrary character splits. Fewer chunks (2189 vs 2596) with higher average quality
after quality filter (MIN_CHUNK_CHARS=40, high-signal exception).

## Hybrid retrieval weighting

**Status:** DECIDED — alpha=0.7 with intfloat/e5-small-v2 is the final retrieval configuration.

Formula: `score = alpha * dense_norm + (1 - alpha) * tfidf_norm`
Both scores min-max normalized to [0, 1] per question before combining.

Full sweep on 25 golden examples, 2189 section-aware chunks:

| Model | Alpha | hit@5 | recall@5 | mrr@10 | latency(s) |
|---|---|---|---|---|---|
| TF-IDF only | 0.0 | 0.360 | 0.360 | 0.194 | 0.1 |
| Dense MiniLM-L6-v2 | 1.0 | 0.480 | 0.480 | 0.209 | 20.6 |
| Dense BGE-small | 1.0 | 0.520 | 0.520 | 0.282 | 175.9 |
| Hybrid BGE-small | 0.7 | 0.560 | 0.560 | 0.327 | 5.3 |
| BGE-small + reranker | 0.7 | 0.600 | 0.600 | 0.316 | 167.0 |
| Dense E5-small-v2 | 1.0 | 0.600 | 0.600 | 0.3307 | 170.1 |
| Hybrid E5 | 0.3 | 0.520 | 0.520 | 0.228 | 5.4 |
| Hybrid E5 | 0.5 | 0.600 | 0.600 | 0.262 | 6.7 |
| **Hybrid E5** | **0.7** | **0.680** | **0.680** | **0.329** | **5.4** |
| E5 + reranker | 0.7 | 0.560 | 0.560 | 0.312 | 6.4 |

**Best alpha: 0.7 with intfloat/e5-small-v2** — highest hit@5 (0.68, +8pp over any prior config) and near-best mrr@10 (0.329, only 0.001 below pure-dense E5) at 31× lower latency.

Higher dense weight (0.7) preserves E5 semantic encoding; sparse (0.3) adds exact-match signal for Kubernetes vocabulary (`kubectl`, `namespace`, `pod`) missing from embedding space.

## Reranker

**Status:** COMPLETE — evaluated with both BGE-small and E5. Not selected for final pipeline.

| Configuration | hit@5 | mrr@10 | latency(s) | Decision |
|---|---|---|---|---|
| Hybrid BGE-small alpha=0.7 | 0.560 | 0.327 | 5.3 | ablation baseline |
| BGE-small + reranker | 0.600 | 0.316 | 167.0 | ablation only |
| **Hybrid E5 alpha=0.7** | **0.680** | **0.329** | **5.4** | **CHOSEN** |
| E5 + reranker | 0.560 | 0.312 | 6.4 | rejected — hurts both metrics |

Reranker degrades E5 hybrid: hit@5 drops 0.68→0.56, mrr@10 drops 0.329→0.312.
The cross-encoder reorders top-20 retrieved by quality, but E5 hybrid already retrieves the
right chunks at rank 1-5 more reliably than BGE-small; the reranker then misorders them.

**Final pipeline: E5 hybrid alpha=0.7, no reranker.**

## Query transformation

**Status:** COMPLETE — deterministic technical_terms expansion evaluated.

| Retriever | Baseline | +technical_terms | hit@5 delta | mrr@10 delta |
|---|---|---|---|---|
| TF-IDF | hit@5=0.36, mrr@10=0.19 | hit@5=0.44, mrr@10=0.20 | **+0.08** | +0.009 |
| Dense BGE-small | hit@5=0.52, mrr@10=0.28 | hit@5=0.52, mrr@10=0.29 | 0.00 | +0.004 |

technical_terms expansion: appends Kubernetes vocabulary tokens and CamelCase identifiers from the question.
- Large hit@5 gain for TF-IDF (+8pp): bag-of-words benefits from repeated exact terms.
- Marginal gain for dense: semantic embedding already captures term meaning; appending raw tokens adds noise.

**Decision:** technical_terms enabled by default for TF-IDF; optional (off by default) for dense retrieval.

## Memory choice
Chosen long-term memory type: episodic

Reason:
Episodic memory is easiest to demonstrate across conversations and fits maintainer
preferences/actions.

## Redis TTL
Short-term memory TTL: 24 hours

Reason:
Preserves active triage context across breaks without keeping temporary debugging
context forever.

## Tracing backend

**Decision:** Jaeger all-in-one (local Docker) + OpenTelemetry SDK with OTLP HTTP exporter.

**Why Jaeger:**
- Single Docker container (`jaegertracing/all-in-one:1.57`); no API key or external account required.
- Ships a browser UI at `http://localhost:16686` — search by service, trace, and tag.
- Accepts OTLP natively on HTTP (port 4318) and gRPC (port 4317) since v1.35.
- Zero operational cost for a local demo: `docker compose up` starts everything.

**Implementation:**
- `app/infra/tracing.py`: `OtelTracerWrapper` wraps OTEL SDK tracer with the existing `start_span(name)` interface. `configure_tracing()` initializes a `TracerProvider` with `BatchSpanProcessor` + `OTLPSpanExporter` when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- NoOpTracer remains the default for local `pytest` runs (no Jaeger needed).
- docker-compose.yml: `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces` wired into the `api` service; tracing is on by default in Docker and off locally.
- `opentelemetry-exporter-otlp-proto-http` added to `pyproject.toml`; requires `uv sync` to install.
- Falls back to `ConsoleSpanExporter` if the OTLP package is not installed.

**Trace attributes in use:**
`chat.request`, `llm.groq.chat`, `tool.{name}`, `rag.retrieve`, `memory.short_term.write`, `auth.register`, `auth.login`, `auth.me`.

## Widget bundle target
TODO
