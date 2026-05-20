"""
Fetch clean kubernetes/kubernetes support-only issues for question examples.

Usage:
    uv run python ml/fetch_clean_support.py --target-count 1000
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_REPO = "kubernetes/kubernetes"
DEFAULT_TARGET_COUNT = 1000
DEFAULT_OUTPUT = Path("data/raw/kubernetes_support_only_extra.jsonl")
DEFAULT_EXISTING_INPUT = Path("data/raw/kubernetes_issues.jsonl")
REPORT_PATH = Path("reports/clean_support_fetch_report.json")
GITHUB_API = "https://api.github.com"
SEARCH_PAGE_DELAY_SECONDS = 2.5
SEARCH_PAGE_LIMIT = 10


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
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_github_token() -> str | None:
    load_dotenv()
    vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.environ.get("VAULT_DEV_ROOT_TOKEN")
    if not vault_token:
        warn("VAULT_DEV_ROOT_TOKEN not set; continuing unauthenticated.")
        return None

    try:
        from app.infra.vault_client import VaultClient

        token = VaultClient(addr=vault_addr, token=vault_token).get_secret_from_path(
            path="github",
            key="token",
        )
    except Exception as exc:  # noqa: BLE001
        warn(f"Vault GitHub token lookup failed; continuing unauthenticated. {exc}")
        return None

    token = token.strip()
    if not token:
        warn("Vault secret/github key token is empty; continuing unauthenticated.")
        return None
    print("Using GitHub token from Vault.")
    return token


def github_get(
    path: str,
    token: str | None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{GITHUB_API}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "handyman-clean-support-fetcher",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except http.client.IncompleteRead:
            if attempt == 2:
                raise RuntimeError(f"Incomplete response after 3 attempts for {path}")
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
            if exc.code == 422:
                raise RuntimeError(
                    "GitHub Search API validation failed. "
                    "Check repository, label names, and date-window query. "
                    f"Response: {body}"
                ) from exc
            raise RuntimeError(
                f"GitHub API error {exc.code} for {path}: {body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"GitHub API request failed for {path}: {exc}") from exc
    raise RuntimeError(f"GitHub API request failed after retries for {path}")


def build_query(repo: str, before_created_at: str | None) -> str:
    query = (
        f'repo:{repo} is:issue is:closed label:"kind/support" '
        '-label:"kind/bug" -label:"kind/feature" -label:"kind/documentation"'
    )
    if before_created_at:
        query = f"{query} created:<{before_created_at}"
    return query


def issue_to_record(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_number": issue["number"],
        "title": issue.get("title") or "",
        "body": issue.get("body") or "",
        "raw_labels": [label["name"] for label in issue.get("labels", [])],
        "final_label": "question",
        "fetch_source": "clean_support_only",
        "created_at": issue.get("created_at"),
        "closed_at": issue.get("closed_at"),
        "updated_at": issue.get("updated_at"),
        "html_url": issue.get("html_url") or "",
    }


def read_existing_issue_numbers(path: Path) -> set[int]:
    if not path.exists():
        return set()

    issue_numbers: set[int] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            issue_number = record.get("issue_number")
            if isinstance(issue_number, int):
                issue_numbers.add(issue_number)
    return issue_numbers


def fetch_support_only(
    repo: str,
    target_count: int,
    token: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records_by_number: dict[int, dict[str, Any]] = {}
    windows_queried: list[dict[str, Any]] = []
    before_created_at: str | None = None

    while len(records_by_number) < target_count:
        window_start_count = len(records_by_number)
        oldest_created_at: str | None = None
        query = build_query(repo, before_created_at)
        window: dict[str, Any] = {
            "before_created_at": before_created_at,
            "pages": 0,
            "items_seen": 0,
            "new_records": 0,
        }

        for page in range(1, SEARCH_PAGE_LIMIT + 1):
            if len(records_by_number) >= target_count:
                break
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
            items = response.get("items", [])
            if not items:
                break

            window["pages"] += 1
            window["items_seen"] += len(items)
            for issue in items:
                issue_number = issue["number"]
                if issue_number not in records_by_number:
                    records_by_number[issue_number] = issue_to_record(issue)
                oldest_created_at = issue.get("created_at") or oldest_created_at
                if len(records_by_number) >= target_count:
                    break

            if len(items) < 100:
                break
            time.sleep(SEARCH_PAGE_DELAY_SECONDS)

        window["new_records"] = len(records_by_number) - window_start_count
        windows_queried.append(window)

        if len(records_by_number) >= target_count:
            break
        if window["items_seen"] == 0 or not oldest_created_at:
            break
        if oldest_created_at == before_created_at:
            break
        before_created_at = oldest_created_at
        time.sleep(SEARCH_PAGE_DELAY_SECONDS)

    return list(records_by_number.values())[:target_count], windows_queried


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / ".gitkeep").touch(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_report(report: dict[str, Any], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / ".gitkeep").touch(exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch clean support-only Kubernetes closed issues."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--target-count", type=int, default=DEFAULT_TARGET_COUNT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--existing-input", type=Path, default=DEFAULT_EXISTING_INPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output == args.existing_input:
        print("ERROR: output must not overwrite existing raw dataset.", file=sys.stderr)
        return 1

    token = get_github_token()
    records, windows_queried = fetch_support_only(args.repo, args.target_count, token)
    existing_issue_numbers = read_existing_issue_numbers(args.existing_input)
    fetched_issue_numbers = {record["issue_number"] for record in records}
    duplicate_vs_existing = len(fetched_issue_numbers & existing_issue_numbers)
    new_unique_vs_existing = len(fetched_issue_numbers - existing_issue_numbers)

    write_jsonl(records, args.output)
    report = {
        "target_count": args.target_count,
        "fetched_total": len(records),
        "new_unique_vs_existing": new_unique_vs_existing,
        "duplicate_vs_existing": duplicate_vs_existing,
        "output_path": str(args.output),
        "windows_queried": windows_queried,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
    write_report(report)

    print(f"fetched_total: {len(records)}")
    print(f"new_unique_vs_existing: {new_unique_vs_existing}")
    print(f"duplicate_vs_existing: {duplicate_vs_existing}")
    print(f"output: {args.output}")
    print(f"report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
