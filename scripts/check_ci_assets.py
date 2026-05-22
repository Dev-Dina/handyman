"""Check CI-required assets are present before running eval jobs.

Run as the first step in the ci-assets job. If any required file is missing,
this script exits 1 with a clear per-file message. Downstream eval jobs use
`if: always()` + an explicit result check so they fail (not skip) when this
job fails — preventing a silent partial-green CI.

Note: artifacts/ and data/ are gitignored. These files must exist from a prior
pipeline run or be restored from MinIO before CI eval jobs can succeed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Each tuple: (file_path, downstream_job_name)
REQUIRED_ASSETS: list[tuple[str, str]] = [
    ("artifacts/classical/best_model.joblib", "classifier-golden-eval"),
    ("evals/golden/classification_golden.jsonl", "classifier-golden-eval"),
    ("evals/golden/rag/rag_golden.jsonl", "rag-golden-eval"),
    ("eval_thresholds.yaml", "classifier-golden-eval, rag-golden-eval"),
    ("data/rag/chunks/chunks_section_aware.jsonl", "rag-golden-eval"),
]


def main() -> None:
    missing: list[str] = []
    for path_str, used_by in REQUIRED_ASSETS:
        path = Path(path_str)
        if path.exists():
            print(f"  OK  {path_str}")
        else:
            print(f"MISS  {path_str}  [needed by: {used_by}]")
            missing.append(path_str)

    print()
    if missing:
        print(f"ERROR: {len(missing)} required asset(s) missing.")
        print(
            "       artifacts/ and data/ are gitignored — not present on a fresh clone."
        )
        print(
            "       Restore from MinIO or re-run the pipeline before eval jobs can pass."
        )
        sys.exit(1)

    print("All CI assets present.")


if __name__ == "__main__":
    main()
