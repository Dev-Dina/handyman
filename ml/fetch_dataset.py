"""
Fetch labeled closed issues from a GitHub repository, per target class.

Uses the GitHub Search API with label-specific queries so that each target class
is sampled up to --per-class issues independently.  Issues appearing in multiple
class queries are deduplicated by issue_number (first-seen wins; GitHub returns
all labels on every response, so the label set is identical across occurrences).

Usage:
    uv run python ml/fetch_dataset.py
    uv run python ml/fetch_dataset.py --repo kubernetes/kubernetes --per-class 1000

Output: data/raw/kubernetes_issues.jsonl
Each record contains raw_labels (all GitHub labels on the issue) so downstream
multi-label conflict resolution is fully transparent.

GitHub token is read from Vault (secret/github, key: token).
Set VAULT_ADDR and VAULT_DEV_ROOT_TOKEN in .env or environment.

Rate limits (authenticated):
    Search API: 30 req/min  → _SEARCH_PAGE_DELAY = 2.5 s between pages
    4 classes × 10 pages = 40 requests ≈ 100 s total
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_REPO = "kubernetes/kubernetes"
DEFAULT_PER_CLASS = 1000
OUTPUT_PATH = Path("data/raw/kubernetes_issues.jsonl")
GITHUB_API = "https://api.github.com"
_SEARCH_PAGE_DELAY = 2.5  # seconds between Search API pages (30 req/min limit)

# Labels to fetch; each drives one Search API query
TARGET_LABELS = [
    "kind/bug",
    "kind/feature",
    "kind/documentation",
    "kind/support",
]


def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_github_token() -> str | None:
    _load_dotenv()
    vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.environ.get("VAULT_DEV_ROOT_TOKEN")
    if not vault_token:
        warn(
            "VAULT_DEV_ROOT_TOKEN not set. "
            "Set VAULT_ADDR and VAULT_DEV_ROOT_TOKEN in .env or environment. "
            "Continuing unauthenticated (60 req/hr limit applies)."
        )
        return None
    try:
        from app.infra.vault_client import VaultClient

        client = VaultClient(addr=vault_addr, token=vault_token)
        token = client.get_secret_from_path(path="github", key="token").strip()
        if token:
            print("Using GitHub token from Vault.")
            return token
        warn("secret/github key 'token' is empty; continuing unauthenticated.")
    except Exception as exc:  # noqa: BLE001
        warn(f"Vault lookup failed; continuing unauthenticated. {exc}")
    return None


def _github_get(
    path: str, token: str | None, params: dict[str, Any] | None = None
) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    req = Request(
        f"{GITHUB_API}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "handyman-dataset-fetcher",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except http.client.IncompleteRead:
            if attempt == 2:
                raise RuntimeError(
                    f"IncompleteRead after 3 attempts for {path}"
                ) from None
            time.sleep(2**attempt)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            rate_remaining = exc.headers.get("X-RateLimit-Remaining")
            rate_reset = exc.headers.get("X-RateLimit-Reset")
            if exc.code in {403, 429} and rate_remaining == "0":
                raise RuntimeError(
                    "GitHub API rate limit reached. "
                    f"Reset epoch: {rate_reset or 'unknown'}. "
                    "Store a GitHub token in Vault at secret/github key token."
                ) from exc
            raise RuntimeError(
                f"GitHub API error {exc.code} for {path}: {body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"GitHub API request failed for {path}: {exc}") from exc
    raise RuntimeError(f"GitHub API request failed after retries for {path}")


def fetch_class_issues(
    repo: str,
    label: str,
    token: str | None,
    per_class: int,
) -> list[dict[str, Any]]:
    """Fetch closed issues for a single target label via GitHub Search API.

    Search API returns up to 1000 results per query (10 pages × 100).
    Issues are sorted newest-first so we get the most recent per_class issues.
    PRs are excluded by the is:issue qualifier.
    """
    issues: list[dict[str, Any]] = []
    # Search API hard-caps at 10 pages × 100 = 1000 results
    max_pages = min((per_class + 99) // 100, 10)
    q = f'repo:{repo} is:issue is:closed label:"{label}"'
    print(f'  label="{label}": fetching up to {per_class} issues…')

    for page in range(1, max_pages + 1):
        if len(issues) >= per_class:
            break
        try:
            resp = _github_get(
                "/search/issues",
                token,
                {
                    "q": q,
                    "sort": "created",
                    "order": "desc",
                    "per_page": 100,
                    "page": page,
                },
            )
        except RuntimeError as exc:
            warn(f'  interrupted at page {page} for label="{label}": {exc}')
            break

        items = resp.get("items", [])
        if not items:
            break

        remaining = per_class - len(issues)
        issues.extend(items[:remaining])
        print(
            f"    page {page}: +{min(len(items), remaining)} "
            f"(class total: {len(issues)})"
        )

        if len(items) < 100:
            break

        try:
            time.sleep(_SEARCH_PAGE_DELAY)
        except KeyboardInterrupt:
            warn(f"  interrupted. Got {len(issues)} for label={label}.")
            break

    return issues


def merge_issues(
    batches: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Deduplicate issues appearing in multiple class queries.

    GitHub returns the full label set on every API response, so the first
    occurrence already contains all target labels.  First-seen wins.
    """
    seen: dict[int, dict[str, Any]] = {}
    for batch in batches.values():
        for issue in batch:
            num = issue["number"]
            if num not in seen:
                seen[num] = issue
    return list(seen.values())


def _to_record(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_number": issue["number"],
        "title": issue.get("title") or "",
        "body": issue.get("body") or "",
        "raw_labels": [lbl["name"] for lbl in issue.get("labels", [])],
        "created_at": issue.get("created_at"),
        "closed_at": issue.get("closed_at"),
        "updated_at": issue.get("updated_at"),
        "html_url": issue.get("html_url") or "",
    }


def save_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / ".gitkeep").touch(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch labeled closed issues from GitHub per target class."
    )
    p.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo")
    p.add_argument(
        "--per-class",
        type=int,
        default=DEFAULT_PER_CLASS,
        help="maximum closed issues to fetch per target label (max 1000, Search API limit)",
    )
    p.add_argument("--output", type=Path, default=OUTPUT_PATH, help="output JSONL path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    token = get_github_token()

    batches: dict[str, list[dict[str, Any]]] = {}
    for label in TARGET_LABELS:
        try:
            batches[label] = fetch_class_issues(args.repo, label, token, args.per_class)
        except RuntimeError as exc:
            warn(f"Failed to fetch label={label}: {exc}. Continuing.")
            batches[label] = []

    per_class_totals = {lbl: len(batch) for lbl, batch in batches.items()}
    all_issues = merge_issues(batches)

    print(f"\nper-class totals (pre-dedup): {per_class_totals}")
    print(f"unique issues after dedup:    {len(all_issues)}")

    if not all_issues:
        print("ERROR: no issues fetched.", file=sys.stderr)
        return 1

    records = [_to_record(i) for i in all_issues]
    save_jsonl(records, args.output)
    print(f"Saved {len(records)} issue records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
