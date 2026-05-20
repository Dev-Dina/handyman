"""
LLM baseline classifier using a local Ollama endpoint.

Evaluates zero-shot classification on the official test split.
No API keys required. No Vault. No training.

Usage:
    # Smoke run (10 rows)
    uv run python ml/llm_baseline.py --limit 10

    # Full run
    uv run python ml/llm_baseline.py

    # Resume interrupted run
    uv run python ml/llm_baseline.py --run-name my_run --resume

Outputs:
    reports/llm/<run_name>/llm_eval.json
    reports/llm/<run_name>/llm_predictions.csv
    reports/llm/<run_name>/llm_raw_responses.jsonl
    reports/llm/llm_runs_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.classifier_config import (  # noqa: E402
    CLASSICAL_TEST_MACRO_F1,
    CODEBERT_TEST_MACRO_F1,
    DEFAULT_LLM_MAX_CHARS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    LABEL_DEFINITIONS,
    LABELS,
    OFFICIAL_LLM_REPORT_DIR,
    OFFICIAL_TEST_PATH,
)

_label_lines = "\n".join(f"- {lbl}: {defn}" for lbl, defn in LABEL_DEFINITIONS.items())
_labels_str = "|".join(LABELS)

_SYSTEM_PROMPT = f"""\
You are a GitHub issue classifier for the kubernetes/kubernetes project.
Classify each issue into exactly one of these four categories:

{_label_lines}

Respond ONLY with valid JSON matching this exact schema:
{{"label": "{_labels_str}", "confidence": 0.0-1.0, "reason": "one sentence"}}

Rules:
- label must be exactly one of: {", ".join(LABELS)}
- confidence is a float between 0.0 and 1.0
- reason is a single sentence explaining the key signal
- Do not include any text outside the JSON object
- Do not add markdown code fences\
"""

_USER_TEMPLATE = """\
Classify this GitHub issue. Reply with JSON only.

Issue title: {title}

Issue body (truncated):
{body_preview}

JSON response:\
"""

_COMPARISON = {
    "classical_logreg_test_macro_f1": CLASSICAL_TEST_MACRO_F1,
    "codebert_test_macro_f1": CODEBERT_TEST_MACRO_F1,
}


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pure_metrics(preds: list[str], refs: list[str]) -> dict:
    n = len(refs)
    accuracy = sum(p == r for p, r in zip(preds, refs)) / n if n else 0.0
    per_class: dict[str, dict] = {}
    for label in LABELS:
        tp = sum(1 for p, r in zip(preds, refs) if p == label and r == label)
        fp = sum(1 for p, r in zip(preds, refs) if p == label and r != label)
        fn = sum(1 for p, r in zip(preds, refs) if p != label and r == label)
        support = sum(1 for r in refs if r == label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        weighted_f1_num = f1 * support
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
            "_weighted_f1_num": weighted_f1_num,
        }
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(per_class)
    weighted_f1 = (
        sum(v["_weighted_f1_num"] for v in per_class.values()) / n if n else 0.0
    )
    for v in per_class.values():
        del v["_weighted_f1_num"]
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
    }


def _ollama_chat(
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    timeout: int,
) -> str:
    """Call Ollama /api/chat and return the assistant message content."""
    try:
        import httpx
    except ImportError:
        from urllib import request as _req

        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            }
        ).encode("utf-8")
        req = _req.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _req.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["message"]["content"]

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _parse_label_response(raw: str) -> dict | None:
    """Extract and validate JSON from model response. Returns None if invalid."""
    text = raw.strip()
    # strip markdown fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.startswith("```")).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # try finding the first { ... } block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end])
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, dict):
        return None
    label = str(parsed.get("label", "")).strip().lower()
    if label not in LABELS:
        return None
    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    reason = str(parsed.get("reason", ""))
    return {"label": label, "confidence": round(confidence, 4), "reason": reason}


def _load_already_done(raw_path: Path) -> set[str]:
    done: set[str] = set()
    if not raw_path.exists():
        return done
    with raw_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("predicted_label") and obj["predicted_label"] != "invalid":
                    done.add(str(obj["issue_number"]))
            except json.JSONDecodeError:
                continue
    return done


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")


def _sanitize(name: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="LLM zero-shot issue classifier via Ollama."
    )
    p.add_argument("--run-name", type=str, default=None)
    p.add_argument("--input", type=Path, default=OFFICIAL_TEST_PATH)
    p.add_argument(
        "--limit", type=int, default=None, help="Smoke run: evaluate only N rows."
    )
    p.add_argument("--resume", type=lambda x: x.lower() != "false", default=True)
    p.add_argument("--base-url", type=str, default=DEFAULT_OLLAMA_BASE_URL)
    p.add_argument("--model", type=str, default=DEFAULT_OLLAMA_MODEL)
    p.add_argument("--temperature", type=float, default=DEFAULT_LLM_TEMPERATURE)
    p.add_argument("--max-chars", type=int, default=DEFAULT_LLM_MAX_CHARS)
    p.add_argument("--reports-dir", type=Path, default=OFFICIAL_LLM_REPORT_DIR)
    p.add_argument("--timeout-seconds", type=int, default=DEFAULT_LLM_TIMEOUT_SECONDS)
    return p.parse_args()


def _update_runs_summary(summary_path: Path, row: dict) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_name",
        "model",
        "provider",
        "input_rows",
        "valid_predictions",
        "invalid_count",
        "accuracy",
        "macro_f1",
        "weighted_f1",
        "question_f1",
        "total_latency_seconds",
        "avg_latency_seconds",
        "cost",
        "timestamp",
    ]
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
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(existing)


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        print(f"ERROR: {args.input} not found.", file=sys.stderr)
        return 1

    timestamp = datetime.now(tz=UTC).isoformat()
    if args.run_name:
        run_name = args.run_name
    else:
        slug = _sanitize(args.model)
        ts_short = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
        run_name = f"ollama_{slug}_{ts_short}"

    run_dir = args.reports_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_path = run_dir / "llm_raw_responses.jsonl"
    preds_path = run_dir / "llm_predictions.csv"
    eval_path = run_dir / "llm_eval.json"
    summary_path = args.reports_dir / "llm_runs_summary.csv"

    rows = _read_csv(args.input)
    if args.limit:
        rows = rows[: args.limit]

    already_done: set[str] = set()
    if args.resume:
        already_done = _load_already_done(raw_path)
        if already_done:
            print(f"Resuming: {len(already_done)} rows already done, skipping.")

    total_rows = len(rows)
    predictions: list[dict] = []
    total_latency = 0.0
    invalid_count = 0

    # load already-completed predictions into memory for final eval
    if already_done and raw_path.exists():
        with raw_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("issue_number"):
                        predictions.append(obj)
                        total_latency += float(obj.get("latency_seconds", 0.0))
                        if obj.get("predicted_label") == "invalid":
                            invalid_count += 1
                except json.JSONDecodeError:
                    continue

    to_predict = [r for r in rows if str(r.get("issue_number", "")) not in already_done]
    print(
        f"run={run_name}  model={args.model}  rows={total_rows}  to_predict={len(to_predict)}"
    )

    for idx, row in enumerate(to_predict, start=1):
        issue_number = str(row.get("issue_number", ""))
        true_label = str(row.get("final_label", "")).strip().lower()
        title = str(row.get("title") or "").strip()
        body = str(row.get("model_text") or row.get("body") or "")
        body_preview = body[: args.max_chars]

        user_msg = _USER_TEMPLATE.format(title=title, body_preview=body_preview)

        predicted = None
        raw_response = ""
        t0 = time.perf_counter()
        for attempt in range(3):
            try:
                raw_response = _ollama_chat(
                    base_url=args.base_url,
                    model=args.model,
                    system=_SYSTEM_PROMPT,
                    user=user_msg,
                    temperature=args.temperature,
                    timeout=args.timeout_seconds,
                )
                predicted = _parse_label_response(raw_response)
                if predicted is not None:
                    break
                print(
                    f"  [{idx}/{len(to_predict)}] #{issue_number} invalid JSON attempt {attempt + 1}/3"
                )
            except Exception as exc:
                print(
                    f"  [{idx}/{len(to_predict)}] #{issue_number} request error attempt {attempt + 1}/3: {exc}"
                )
                if attempt < 2:
                    time.sleep(2)

        latency = round(time.perf_counter() - t0, 3)
        total_latency += latency

        if predicted is None:
            predicted_label = "invalid"
            confidence = 0.0
            reason = ""
            invalid_count += 1
        else:
            predicted_label = predicted["label"]
            confidence = predicted["confidence"]
            reason = predicted["reason"]

        record = {
            "issue_number": issue_number,
            "true_label": true_label,
            "predicted_label": predicted_label,
            "confidence": confidence,
            "reason": reason,
            "latency_seconds": latency,
            "raw_response": raw_response,
        }
        _append_jsonl(raw_path, record)
        predictions.append(record)

        match = "✓" if predicted_label == true_label else "✗"
        print(
            f"  [{idx}/{len(to_predict)}] #{issue_number}"
            f"  true={true_label}  pred={predicted_label}"
            f"  {match}  {latency:.1f}s"
        )

    # write predictions CSV (all valid rows, excluding invalid)
    valid_preds = [p for p in predictions if p["predicted_label"] != "invalid"]
    with preds_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "issue_number",
                "true_label",
                "predicted_label",
                "confidence",
                "reason",
                "latency_seconds",
            ],
        )
        writer.writeheader()
        for p in predictions:
            writer.writerow(
                {
                    "issue_number": p["issue_number"],
                    "true_label": p["true_label"],
                    "predicted_label": p["predicted_label"],
                    "confidence": p["confidence"],
                    "reason": p["reason"],
                    "latency_seconds": p["latency_seconds"],
                }
            )

    # metrics on valid predictions only
    if valid_preds:
        pred_labels = [p["predicted_label"] for p in valid_preds]
        ref_labels = [p["true_label"] for p in valid_preds]
        metrics = _pure_metrics(pred_labels, ref_labels)
    else:
        metrics = {
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "per_class": {},
        }

    avg_latency = round(total_latency / max(len(predictions), 1), 3)
    question_f1 = metrics.get("per_class", {}).get("question", {}).get("f1", 0.0)

    eval_report = {
        "run_name": run_name,
        "model": args.model,
        "provider": "ollama_local",
        "base_url": args.base_url,
        "temperature": args.temperature,
        "max_chars": args.max_chars,
        "input_path": str(args.input),
        "input_rows": total_rows,
        "evaluated_rows": len(predictions),
        "valid_predictions": len(valid_preds),
        "invalid_count": invalid_count,
        "metrics": metrics,
        "latency": {
            "total_seconds": round(total_latency, 3),
            "avg_seconds": avg_latency,
        },
        "cost": 0,
        "comparison_context": _COMPARISON,
        "timestamp": timestamp,
    }

    _write_json(eval_path, eval_report)

    _update_runs_summary(
        summary_path,
        {
            "run_name": run_name,
            "model": args.model,
            "provider": "ollama_local",
            "input_rows": total_rows,
            "valid_predictions": len(valid_preds),
            "invalid_count": invalid_count,
            "accuracy": metrics.get("accuracy", ""),
            "macro_f1": metrics.get("macro_f1", ""),
            "weighted_f1": metrics.get("weighted_f1", ""),
            "question_f1": question_f1,
            "total_latency_seconds": round(total_latency, 3),
            "avg_latency_seconds": avg_latency,
            "cost": 0,
            "timestamp": timestamp,
        },
    )

    print(f"\naccuracy:   {metrics.get('accuracy', 0)}")
    print(f"macro_f1:   {metrics.get('macro_f1', 0)}")
    print(f"invalid:    {invalid_count}/{total_rows}")
    print(f"latency:    {round(total_latency, 1)}s total  {avg_latency}s avg")
    print(f"eval:       {eval_path}")
    print(f"preds:      {preds_path}")
    print(f"summary:    {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
