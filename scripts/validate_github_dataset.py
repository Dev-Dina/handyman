"""
Validate whether a GitHub repository has enough labeled closed issues for
the project classification dataset.

Default:
    uv run python scripts/validate_github_dataset.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.domain.errors import SecretNotFoundError, VaultUnavailableError

DEFAULT_REPO = "kubernetes/kubernetes"
DEFAULT_SAMPLE_SIZE = 300
REPORT_PATH = Path("reports/dataset_validation_kubernetes.json")
GITHUB_API = "https://api.github.com"
SEARCH_PAGE_LIMIT = 10

# Kubernetes target labels only — exact match, no normalisation required
DRAFT_LABEL_MAPPING: dict[str, str] = {
    "kind/bug": "bug",
    "kind/feature": "feature",
    "kind/documentation": "docs",
    "kind/support": "question",
}

TARGET_CLASSES = ("bug", "feature", "docs", "question")


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_github_token_from_vault() -> str | None:
    load_dotenv()
    vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.environ.get("VAULT_DEV_ROOT_TOKEN")
    if not vault_token:
        warn("Vault token missing; continuing unauthenticated.")
        return None

    try:
        from app.infra.vault_client import VaultClient

        client = VaultClient(addr=vault_addr, token=vault_token)
        token = client.get_secret_from_path(path="github", key="token").strip()
        if token:
            print("Using GitHub token from Vault.")
            return token
        warn(
            "Vault is available, but secret/github key 'token' is empty; continuing unauthenticated."
        )
    except SecretNotFoundError:
        warn(
            "secret/github key 'token' not found in Vault; continuing unauthenticated."
        )
    except VaultUnavailableError as exc:
        warn(
            f"Vault unavailable for GitHub token lookup; continuing unauthenticated. {exc}"
        )
    except ImportError as exc:
        warn(f"Vault client unavailable; continuing unauthenticated. {exc}")
    return None


def github_get(
    path: str, token: str | None, params: dict[str, Any] | None = None
) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{GITHUB_API}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "handyman-dataset-validator",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        rate_remaining = exc.headers.get("X-RateLimit-Remaining")
        rate_reset = exc.headers.get("X-RateLimit-Reset")
        if exc.code in {403, 429} and rate_remaining == "0":
            raise RuntimeError(
                "GitHub API rate limit reached. "
                f"Reset epoch: {rate_reset or 'unknown'}. "
                "Add a GitHub token to Vault or retry later."
            ) from exc
        if exc.code == 422:
            raise RuntimeError(
                f"GitHub API validation failed for {path}. "
                "Check query parameters and repository name. "
                f"Response: {body}"
            ) from exc
        raise RuntimeError(f"GitHub API error {exc.code} for {path}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API request failed for {path}: {exc}") from exc


def fetch_all_labels(repo: str, token: str | None) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = github_get(
            f"/repos/{repo}/labels",
            token,
            {"per_page": 100, "page": page},
        )
        if not batch:
            return labels
        labels.extend(batch)
        page += 1


def fetch_closed_issue_sample(
    repo: str,
    token: str | None,
    sample_size: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    page = 1
    before_created_at: str | None = None

    while len(issues) < sample_size:
        query = f"repo:{repo} is:issue is:closed"
        if before_created_at:
            query = f"{query} created:<{before_created_at}"

        response = github_get(
            "/search/issues",
            token,
            {
                "q": query,
                "sort": "created",
                "order": "desc",
                "per_page": 100,
                "page": page,
            },
        )
        batch = response.get("items", [])
        if not batch:
            break

        issues.extend(batch[: sample_size - len(issues)])

        if len(issues) >= sample_size:
            break

        if page < SEARCH_PAGE_LIMIT:
            page += 1
            continue

        oldest_created_at = batch[-1].get("created_at")
        if not oldest_created_at or oldest_created_at == before_created_at:
            break
        before_created_at = oldest_created_at
        page = 1

    return issues


def normalize_label(label: str) -> str:
    return " ".join(label.strip().lower().split())


def mapped_classes(labels: list[str]) -> set[str]:
    # Kubernetes labels are exact; normalization is a no-op but kept for safety
    classes: set[str] = set()
    for label in labels:
        mapped = DRAFT_LABEL_MAPPING.get(
            normalize_label(label)
        ) or DRAFT_LABEL_MAPPING.get(label)
        if mapped:
            classes.add(mapped)
    return classes


def recommendation(
    total: int, usable: int, class_counts: Counter[str], conflicts: int
) -> str:
    if total == 0:
        return "not viable"

    usable_ratio = usable / total
    nonzero_classes = sum(1 for item in TARGET_CLASSES if class_counts[item] > 0)
    smallest_class = min(class_counts[item] for item in TARGET_CLASSES)
    conflict_ratio = conflicts / total

    if (
        usable >= 100
        and usable_ratio >= 0.35
        and nonzero_classes >= 3
        and smallest_class >= 10
    ):
        return "viable" if conflict_ratio <= 0.15 else "risky"
    if usable >= 40 and usable_ratio >= 0.15 and nonzero_classes >= 2:
        return "risky"
    return "not viable"


def build_report(repo: str, sample_size: int, token: str | None) -> dict[str, Any]:
    labels = fetch_all_labels(repo, token)
    issues = fetch_closed_issue_sample(repo, token, sample_size)

    label_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter({target: 0 for target in TARGET_CLASSES})
    unmapped_counts: Counter[str] = Counter()
    conflicts: list[dict[str, Any]] = []
    created_at_values: list[str] = []
    usable = 0

    for issue in issues:
        issue_labels = [label["name"] for label in issue.get("labels", [])]
        label_counts.update(issue_labels)
        created_at = issue.get("created_at")
        if created_at:
            created_at_values.append(created_at)

        classes = mapped_classes(issue_labels)
        if len(classes) == 1:
            usable += 1
            class_counts[next(iter(classes))] += 1
        elif len(classes) > 1:
            conflicts.append(
                {
                    "number": issue.get("number"),
                    "mapped_classes": sorted(classes),
                    "labels": issue_labels,
                }
            )

        for label in issue_labels:
            if normalize_label(label) not in DRAFT_LABEL_MAPPING:
                unmapped_counts[label] += 1

    now = datetime.now(tz=UTC).isoformat()
    return {
        "repo": repo,
        "generated_at": now,
        "github_auth": "vault_token" if token else "unauthenticated",
        "sample_requested": sample_size,
        "total_repo_labels": len(labels),
        "total_sampled_closed_issues": len(issues),
        "usable_mapped_issues": usable,
        "class_counts": dict(class_counts),
        "unmapped_top_labels": [
            {"label": label, "count": count}
            for label, count in unmapped_counts.most_common(20)
        ],
        "multi_label_conflicts": {
            "count": len(conflicts),
            "examples": conflicts[:20],
        },
        "oldest_created_at": min(created_at_values) if created_at_values else None,
        "newest_created_at": max(created_at_values) if created_at_values else None,
        "recommendation": recommendation(
            len(issues), usable, class_counts, len(conflicts)
        ),
        "draft_label_mapping": DRAFT_LABEL_MAPPING,
        "top_sample_labels": [
            {"label": label, "count": count}
            for label, count in label_counts.most_common(30)
        ],
    }


def save_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gitkeep = path.parent / ".gitkeep"
    gitkeep.touch(exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate GitHub issue labels for dataset viability."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo to validate")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help="number of closed non-PR issues to sample",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORT_PATH,
        help="JSON report output path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = get_github_token_from_vault()
    report = build_report(args.repo, args.sample_size, token)
    save_report(report, args.output)

    print(f"repo: {report['repo']}")
    print(f"sampled_closed_issues: {report['total_sampled_closed_issues']}")
    print(f"usable_mapped_issues: {report['usable_mapped_issues']}")
    print(f"class_counts: {report['class_counts']}")
    print(f"recommendation: {report['recommendation']}")
    print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
