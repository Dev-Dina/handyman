# Evaluation

## Classification eval
Golden set:
- 25 hand-curated issues
- separate from train/val/test where possible

Metrics:
- accuracy
- macro-F1
- per-class F1
- confusion matrix

Models:
- classical ML
- fine-tuned transformer
- LLM baseline

Output:
- reports/classification_eval_report.json

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
