"""
Fine-tune a sequence classification model on GitHub issue labels.

Usage:
    uv run python ml/finetune.py --smoke        # quick smoke test (2 steps, tiny model)
    uv run python ml/finetune.py                # full training (distilbert, 3 epochs)

Outputs saved to artifacts/<run_name>/:
    model/          HuggingFace model checkpoint
    model_card.json metadata, hyperparameters, data hash, metrics

Requires ML extras:
    uv sync --extra ml
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

TRAIN_PATH = Path("data/processed/train.csv")
VAL_PATH = Path("data/processed/val.csv")
TEST_PATH = Path("data/processed/test.csv")
ARTIFACTS_DIR = Path("artifacts")

LABELS = ["bug", "docs", "feature", "question"]
LABEL2ID = {lbl: i for i, lbl in enumerate(LABELS)}
ID2LABEL = {i: lbl for lbl, i in LABEL2ID.items()}

FULL_MODEL = "distilbert-base-uncased"
SMOKE_MODEL = "prajjwal1/bert-tiny"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sha256_prefix(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _write_model_card(
    path: Path,
    architecture: str,
    hyperparams: dict,
    data_hash: str,
    split_counts: dict,
    metrics: dict | None,
    timestamp: str,
) -> None:
    card = {
        "architecture": architecture,
        "hyperparameters": hyperparams,
        "data_hash": data_hash,
        "split_counts": split_counts,
        "metrics": metrics,
        "labels": LABELS,
        "label2id": LABEL2ID,
        "timestamp": timestamp,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fine-tune GitHub issue label classifier.")
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke test: prajjwal1/bert-tiny, 2 steps, CPU only.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="HuggingFace model name (overrides default).",
    )
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--max-len", type=int, default=128)
    p.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR)
    p.add_argument(
        "--drop-mostly-non-ascii",
        action="store_true",
        default=False,
        help="Drop rows where non-ASCII ratio >= 0.30 before training.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    for path in (TRAIN_PATH, VAL_PATH, TEST_PATH):
        if not path.exists():
            print(
                f"ERROR: {path} not found. Run ml/split_dataset.py first.",
                file=sys.stderr,
            )
            return 1

    try:
        from datasets import Dataset
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        print(
            f"ERROR: ML deps missing. Run: uv sync --extra ml\n{exc}",
            file=sys.stderr,
        )
        return 1

    model_name = args.model or (SMOKE_MODEL if args.smoke else FULL_MODEL)
    run_name = "smoke" if args.smoke else "full"
    output_dir = args.output_dir / run_name
    output_dir.mkdir(parents=True, exist_ok=True)

    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location(
        "text_preprocessing", Path(__file__).parent / "text_preprocessing.py"
    )
    _mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    preprocess_rows = _mod.preprocess_rows

    train_rows = preprocess_rows(_read_csv(TRAIN_PATH), args.drop_mostly_non_ascii)
    val_rows = preprocess_rows(_read_csv(VAL_PATH), args.drop_mostly_non_ascii)
    test_rows = preprocess_rows(_read_csv(TEST_PATH), args.drop_mostly_non_ascii)

    if args.smoke:
        train_rows = train_rows[:16]
        val_rows = val_rows[:8]
        test_rows = test_rows[:8]

    def _to_dataset(rows: list[dict]) -> Dataset:
        texts = [
            r.get("model_text") or f"{r.get('title', '')} {r.get('body', '')}".strip()
            for r in rows
        ]
        label_ids = [LABEL2ID.get(r.get("final_label", ""), 0) for r in rows]
        return Dataset.from_dict({"text": texts, "label": label_ids})

    from transformers import BertTokenizerFast

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
    except (ValueError, OSError):
        tokenizer = BertTokenizerFast.from_pretrained(model_name)

    def _tokenize(batch: dict) -> dict:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=args.max_len,
            padding="max_length",
        )

    train_ds = _to_dataset(train_rows).map(_tokenize, batched=True)
    val_ds = _to_dataset(val_rows).map(_tokenize, batched=True)
    test_ds = _to_dataset(test_rows).map(_tokenize, batched=True)

    from transformers import BertForSequenceClassification

    try:
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(LABELS),
            id2label=ID2LABEL,
            label2id=LABEL2ID,
            ignore_mismatched_sizes=True,
        )
    except (ValueError, OSError):
        model = BertForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(LABELS),
            id2label=ID2LABEL,
            label2id=LABEL2ID,
            ignore_mismatched_sizes=True,
        )

    if args.smoke:
        training_args = TrainingArguments(
            output_dir=str(output_dir / "checkpoints"),
            max_steps=2,
            per_device_train_batch_size=args.batch_size,
            eval_strategy="no",
            save_strategy="no",
            report_to="none",
            logging_steps=1,
            use_cpu=True,
        )
    else:
        training_args = TrainingArguments(
            output_dir=str(output_dir / "checkpoints"),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size,
            learning_rate=args.lr,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            report_to="none",
            logging_steps=50,
        )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds if not args.smoke else None,
    )

    import torch

    device = "cuda" if torch.cuda.is_available() and not args.smoke else "cpu"
    print(f"model={model_name} smoke={args.smoke} device={device}")
    trainer.train()

    metrics: dict | None = None
    try:
        test_results = trainer.evaluate(test_ds)
        metrics = {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in test_results.items()
        }
    except Exception:  # noqa: BLE001
        pass

    model.save_pretrained(str(output_dir / "model"))
    tokenizer.save_pretrained(str(output_dir / "model"))

    _write_model_card(
        output_dir / "model_card.json",
        architecture=model_name,
        hyperparams={
            "epochs": args.epochs if not args.smoke else 1,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "max_len": args.max_len,
            "smoke": args.smoke,
        },
        data_hash=_sha256_prefix(TRAIN_PATH),
        split_counts={
            "train": len(train_rows),
            "val": len(val_rows),
            "test": len(test_rows),
        },
        metrics=metrics,
        timestamp=datetime.now(tz=UTC).isoformat(),
    )

    print(f"model saved: {output_dir / 'model'}")
    print(f"model card: {output_dir / 'model_card.json'}")
    if metrics:
        print(f"test metrics: {metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
