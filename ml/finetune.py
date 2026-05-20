"""
Fine-tune a sequence classification model on GitHub issue labels.

Usage:
    python ml/finetune.py --smoke                                   # 2-step smoke test, CPU
    python ml/finetune.py                                           # full training, CUDA if available
    python ml/finetune.py --model google/electra-small-discriminator --run-name electra-small

No pandas, no datasets, no Trainer. Uses csv stdlib + torch + transformers.

Outputs:
    artifacts/transformer/<run_name>/model/                             saved model + tokenizer
    artifacts/transformer/<run_name>/model_card.json                    metadata, hyperparams, metrics
    reports/transformer/<run_name>/transformer_eval.json                test-set evaluation
    reports/transformer/<run_name>/transformer_training_history.json    per-epoch log
    reports/transformer/transformer_runs_summary.csv                    cross-run comparison table
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.classifier_config import (  # noqa: E402
    ID2LABEL,
    LABEL2ID,
    LABELS as _LABELS,
    OFFICIAL_TEST_PATH,
    OFFICIAL_TRAIN_PATH,
    OFFICIAL_VAL_PATH,
    OFFICIAL_TRANSFORMER_REPORT_DIR,
)

TRAIN_PATH = OFFICIAL_TRAIN_PATH
VAL_PATH = OFFICIAL_VAL_PATH
TEST_PATH = OFFICIAL_TEST_PATH

ARTIFACTS_BASE = Path("artifacts/transformer")
REPORTS_BASE = OFFICIAL_TRANSFORMER_REPORT_DIR

LABELS = list(_LABELS)
# LABEL2ID and ID2LABEL imported from classifier_config

FULL_MODEL = "distilbert-base-uncased"
SMOKE_MODEL = "prajjwal1/bert-tiny"

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize(name: str) -> str:
    return _UNSAFE_CHARS.sub("_", name)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sha256_prefix(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _load_preprocessor():  # type: ignore[return]
    spec = importlib.util.spec_from_file_location(
        "text_preprocessing", Path(__file__).parent / "text_preprocessing.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.preprocess_rows


def _pure_metrics(preds: list[int], refs: list[int]) -> dict:
    """Accuracy, macro-F1, and per-class P/R/F1 — pure Python, no numpy."""
    n = len(refs)
    accuracy = sum(p == r for p, r in zip(preds, refs)) / n if n else 0.0
    per_class: dict[str, dict] = {}
    for label_id, label_name in ID2LABEL.items():
        tp = sum(1 for p, r in zip(preds, refs) if p == label_id and r == label_id)
        fp = sum(1 for p, r in zip(preds, refs) if p == label_id and r != label_id)
        fn = sum(1 for p, r in zip(preds, refs) if p != label_id and r == label_id)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        per_class[label_name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(per_class)
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
    }


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_model_card(
    path: Path,
    architecture: str,
    hyperparams: dict,
    data_hash: str,
    split_counts: dict,
    metrics: dict | None,
    timestamp: str,
) -> None:
    _write_json(
        path,
        {
            "architecture": architecture,
            "data_hash": data_hash,
            "hyperparameters": hyperparams,
            "label2id": LABEL2ID,
            "labels": LABELS,
            "metrics": metrics,
            "split_counts": split_counts,
            "timestamp": timestamp,
        },
    )


_SUMMARY_FIELDS = [
    "run_name",
    "model",
    "epochs",
    "batch_size",
    "max_len",
    "lr",
    "best_val_macro_f1",
    "test_accuracy",
    "test_macro_f1",
    "question_f1",
    "artifact_path",
    "timestamp",
]


def _update_runs_summary(summary_path: Path, row: dict) -> None:
    """Append or update (matched by run_name) a row in the runs summary CSV."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if summary_path.exists():
        with summary_path.open(encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))
    updated = False
    for i, r in enumerate(existing):
        if r.get("run_name") == row["run_name"]:
            existing[i] = row
            updated = True
            break
    if not updated:
        existing.append(row)
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(existing)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fine-tune GitHub issue label classifier.")
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke test: prajjwal1/bert-tiny, 2 steps, CPU only.",
    )
    p.add_argument(
        "--model", default=None, help="HuggingFace model name (overrides default)."
    )
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--max-len", type=int, default=128)
    p.add_argument("--output-dir", type=Path, default=ARTIFACTS_BASE)
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_BASE,
        help="Base reports directory (default: reports/transformer).",
    )
    p.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this run (used in output paths). Defaults to sanitized model name.",
    )
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
        import torch
        from torch.optim import AdamW
        from torch.utils.data import DataLoader
        from torch.utils.data import Dataset as TorchDataset
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            BertForSequenceClassification,
            BertTokenizerFast,
        )
    except ImportError as exc:
        print(
            f"ERROR: ML deps missing. Install torch + transformers.\n{exc}",
            file=sys.stderr,
        )
        return 1

    # ── dataset ───────────────────────────────────────────────────────────────

    class IssueDataset(TorchDataset):  # type: ignore[type-arg]
        def __init__(self, encodings: dict, labels: list[int]) -> None:
            self._enc = {k: torch.tensor(v) for k, v in encodings.items()}
            self._labels = torch.tensor(labels, dtype=torch.long)

        def __len__(self) -> int:
            return len(self._labels)

        def __getitem__(self, idx: int) -> dict:
            item = {k: v[idx] for k, v in self._enc.items()}
            item["labels"] = self._labels[idx]
            return item

    # ── data loading ──────────────────────────────────────────────────────────

    preprocess_rows = _load_preprocessor()
    train_rows = preprocess_rows(_read_csv(TRAIN_PATH), args.drop_mostly_non_ascii)
    val_rows = preprocess_rows(_read_csv(VAL_PATH), args.drop_mostly_non_ascii)
    test_rows = preprocess_rows(_read_csv(TEST_PATH), args.drop_mostly_non_ascii)

    if args.smoke:
        train_rows = train_rows[:16]
        val_rows = val_rows[:8]
        test_rows = test_rows[:8]

    def _texts(rows: list[dict]) -> list[str]:
        return [
            r.get("model_text") or f"{r.get('title', '')} {r.get('body', '')}".strip()
            for r in rows
        ]

    def _label_ids(rows: list[dict]) -> list[int]:
        return [LABEL2ID.get(r.get("final_label", ""), 0) for r in rows]

    model_name = args.model or (SMOKE_MODEL if args.smoke else FULL_MODEL)

    if args.run_name:
        run_name = args.run_name
    elif args.smoke:
        run_name = "smoke"
    else:
        run_name = _sanitize(model_name)

    output_dir = args.output_dir / run_name
    run_reports_dir = args.reports_dir / run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    run_reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
    except (ValueError, OSError):
        tokenizer = BertTokenizerFast.from_pretrained(model_name)

    def _encode(texts: list[str]) -> dict:
        return dict(
            tokenizer(
                texts,
                truncation=True,
                max_length=args.max_len,
                padding="max_length",
            )
        )

    train_ds = IssueDataset(_encode(_texts(train_rows)), _label_ids(train_rows))
    val_ds = IssueDataset(_encode(_texts(val_rows)), _label_ids(val_rows))
    test_ds = IssueDataset(_encode(_texts(test_rows)), _label_ids(test_rows))

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size)

    # ── model ─────────────────────────────────────────────────────────────────

    device = torch.device(
        "cuda" if torch.cuda.is_available() and not args.smoke else "cpu"
    )
    print(f"model={model_name}  smoke={args.smoke}  device={device}")

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
    model = model.to(device)

    optimizer = AdamW(model.parameters(), lr=args.lr)

    # ── smoke: 2 steps, CPU, no val ───────────────────────────────────────────

    if args.smoke:
        model.train()
        for step, batch in enumerate(train_loader):
            if step >= 2:
                break
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            loss = model(**batch).loss
            loss.backward()
            optimizer.step()
            print(f"  smoke step {step + 1}/2  loss={loss.item():.4f}")

        model.save_pretrained(str(output_dir / "model"))
        tokenizer.save_pretrained(str(output_dir / "model"))
        _write_model_card(
            output_dir / "model_card.json",
            architecture=model_name,
            hyperparams={
                "batch_size": args.batch_size,
                "epochs": 0,
                "lr": args.lr,
                "max_len": args.max_len,
                "smoke": True,
            },
            data_hash=_sha256_prefix(TRAIN_PATH),
            split_counts={
                "train": len(train_rows),
                "val": len(val_rows),
                "test": len(test_rows),
            },
            metrics=None,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        print(f"smoke model saved: {output_dir / 'model'}")
        return 0

    # ── full training loop ────────────────────────────────────────────────────

    def _evaluate(loader: DataLoader) -> dict:  # type: ignore[type-arg]
        model.eval()
        all_preds: list[int] = []
        all_refs: list[int] = []
        total_loss = 0.0
        with torch.no_grad():
            for batch in loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                out = model(**batch)
                total_loss += out.loss.item()
                all_preds.extend(torch.argmax(out.logits, dim=-1).tolist())
                all_refs.extend(batch["labels"].tolist())
        m = _pure_metrics(all_preds, all_refs)
        m["loss"] = round(total_loss / max(len(loader), 1), 4)
        return m

    best_val_macro_f1 = -1.0
    best_state: dict | None = None
    history: list[dict] = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            loss = model(**batch).loss
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        avg_train_loss = round(train_loss / max(len(train_loader), 1), 4)
        val_m = _evaluate(val_loader)

        print(
            f"epoch {epoch}/{args.epochs}  train_loss={avg_train_loss}"
            f"  val_loss={val_m['loss']}  val_macro_f1={val_m['macro_f1']}"
            f"  val_acc={val_m['accuracy']}"
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss": avg_train_loss,
                "val_accuracy": val_m["accuracy"],
                "val_loss": val_m["loss"],
                "val_macro_f1": val_m["macro_f1"],
                "val_per_class": val_m["per_class"],
            }
        )

        if val_m["macro_f1"] > best_val_macro_f1:
            best_val_macro_f1 = val_m["macro_f1"]
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            print(f"  new best val_macro_f1={best_val_macro_f1}")

    # ── restore best, evaluate test ───────────────────────────────────────────

    if best_state is not None:
        model.load_state_dict(best_state)

    test_m = _evaluate(test_loader)
    print(f"\ntest accuracy:  {test_m['accuracy']}")
    print(f"test macro_f1:  {test_m['macro_f1']}")
    for cls, scores in test_m["per_class"].items():
        print(
            f"  {cls}: precision={scores['precision']}"
            f"  recall={scores['recall']}  f1={scores['f1']}"
        )

    # ── save artifacts ────────────────────────────────────────────────────────

    timestamp = datetime.now(tz=UTC).isoformat()

    model.save_pretrained(str(output_dir / "model"))
    tokenizer.save_pretrained(str(output_dir / "model"))

    _write_json(
        run_reports_dir / "transformer_training_history.json",
        {
            "best_val_macro_f1": best_val_macro_f1,
            "epochs": args.epochs,
            "history": history,
            "model": model_name,
            "run_name": run_name,
        },
    )

    _write_json(
        run_reports_dir / "transformer_eval.json",
        {
            "best_val_macro_f1": best_val_macro_f1,
            "model": model_name,
            "run_name": run_name,
            "test_metrics": test_m,
            "timestamp": timestamp,
        },
    )

    _write_model_card(
        output_dir / "model_card.json",
        architecture=model_name,
        hyperparams={
            "batch_size": args.batch_size,
            "epochs": args.epochs,
            "lr": args.lr,
            "max_len": args.max_len,
            "smoke": False,
        },
        data_hash=_sha256_prefix(TRAIN_PATH),
        split_counts={
            "train": len(train_rows),
            "val": len(val_rows),
            "test": len(test_rows),
        },
        metrics=test_m,
        timestamp=timestamp,
    )

    _update_runs_summary(
        args.reports_dir / "transformer_runs_summary.csv",
        {
            "run_name": run_name,
            "model": model_name,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "max_len": args.max_len,
            "lr": args.lr,
            "best_val_macro_f1": best_val_macro_f1,
            "test_accuracy": test_m["accuracy"],
            "test_macro_f1": test_m["macro_f1"],
            "question_f1": test_m["per_class"].get("question", {}).get("f1", ""),
            "artifact_path": str(output_dir),
            "timestamp": timestamp,
        },
    )

    print(f"model saved: {output_dir / 'model'}")
    print(f"model card:  {output_dir / 'model_card.json'}")
    print(f"eval:        {run_reports_dir / 'transformer_eval.json'}")
    print(f"history:     {run_reports_dir / 'transformer_training_history.json'}")
    print(f"summary:     {args.reports_dir / 'transformer_runs_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
