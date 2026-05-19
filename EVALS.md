# Evaluation

## Classification eval

Labels used: kubernetes/kubernetes mapped classes — bug / feature / docs / question
(same 4 classes as label mapping in DECISIONS.md).

Golden set:
- 25 hand-curated Kubernetes issues
- separate from train/val/test where possible

Metrics:
- accuracy
- macro-F1
- per-class F1
- confusion matrix

Models:
- classical ML baseline
- fine-tuned transformer
- LLM baseline

Output:
- reports/classification_eval_report.json

**Note:** Metrics will be populated after real splits and training are complete.
Do not invent or placeholder metric numbers.

## RAG eval

Golden set:
- 25 question / ideal answer / ground-truth chunks triples
- 5 manually judged examples

Metrics:
- hit@5
- MRR@10
- answer relevancy
- faithfulness

Output:
- reports/rag_eval_report.json

## CI gates
Thresholds live in eval_thresholds.yaml.
Thresholds must not be zero or disabled.
