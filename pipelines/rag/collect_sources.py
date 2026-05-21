"""Collect RAG corpus sources: issue comments + bounded curated docs.

Usage:
    python -m pipelines.rag.collect_sources
    python -m pipelines.rag.collect_sources --max-issues 50 --max-comments-per-issue 20 --max-docs 12

Reads:
    data/rag/processed/heldout_issue_candidates.jsonl
    data/processed/train.csv, val.csv, test.csv  (leakage re-check)
    evals/golden/classification_golden.jsonl       (leakage re-check)

Writes:
    data/rag/processed/issues_with_comments.jsonl
    data/rag/raw_docs/doc_sources.jsonl
    data/rag/corpus_manifest.json         (updated)
    reports/rag/corpus_collection_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.paths import EVALS_DIR
from app.services.rag.config import (
    RAG_CORPUS_COLLECTION_REPORT_PATH,
    RAG_CORPUS_MANIFEST_PATH,
    RAG_DOC_SOURCES_PATH,
    RAG_HELDOUT_CANDIDATES_PATH,
    RAG_ISSUES_WITH_COMMENTS_PATH,
    RAG_LEAKAGE_REPORT_PATH,
    SOURCE_TYPE_DOCS,
    SOURCE_TYPE_ISSUE,
)
from ml.classifier_config import (
    OFFICIAL_TEST_PATH,
    OFFICIAL_TRAIN_PATH,
    OFFICIAL_VAL_PATH,
)

GITHUB_API = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_WEB_BASE = "https://github.com"
CLASSIFICATION_GOLDEN_PATH = EVALS_DIR / "golden" / "classification_golden.jsonl"
MAINTAINER_LIKE_ASSOCIATIONS: frozenset[str] = frozenset(
    {"MEMBER", "OWNER", "COLLABORATOR"}
)
_API_DELAY = 0.5  # seconds between GitHub REST API calls

# Curated bounded doc sources: (repo, branch, path)
# kubernetes/kubernetes — core repo docs (branch: master)
# kubernetes/website — official user-facing docs (branch: main)
DOC_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("kubernetes/kubernetes", "master", "README.md"),
    ("kubernetes/kubernetes", "master", "docs/README.md"),
    ("kubernetes/kubernetes", "master", "docs/devel/README.md"),
    ("kubernetes/kubernetes", "master", "docs/contributors/README.md"),
    ("kubernetes/kubernetes", "master", "docs/contributors/devel/README.md"),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/concepts/overview/what-is-kubernetes.md",
    ),
    ("kubernetes/website", "main", "content/en/docs/concepts/architecture/_index.md"),
    ("kubernetes/website", "main", "content/en/docs/concepts/workloads/pods/_index.md"),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/concepts/workloads/controllers/deployment.md",
    ),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/concepts/services-networking/service.md",
    ),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/concepts/services-networking/dns-pod-service.md",
    ),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/concepts/configuration/overview.md",
    ),
    ("kubernetes/website", "main", "content/en/docs/concepts/storage/volumes.md"),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/tasks/debug/debug-application/_index.md",
    ),
    (
        "kubernetes/website",
        "main",
        "content/en/docs/tasks/debug/debug-cluster/_index.md",
    ),
    ("kubernetes/website", "main", "content/en/docs/reference/kubectl/overview.md"),
)


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get_github_token() -> str:
    """Load GitHub token from Vault. Exits with BLOCKER message if unavailable."""
    _load_dotenv()
    vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.environ.get("VAULT_DEV_ROOT_TOKEN")
    if not vault_token:
        print(
            "BLOCKER: VAULT_DEV_ROOT_TOKEN not set. "
            "Set VAULT_ADDR and VAULT_DEV_ROOT_TOKEN in .env or environment. "
            "Start Vault: docker compose up -d vault",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        from app.infra.vault_client import VaultClient  # noqa: PLC0415

        client = VaultClient(addr=vault_addr, token=vault_token)
        token = client.get_secret_from_path(path="github", key="token").strip()
        if not token:
            print(
                "BLOCKER: secret/github key 'token' is empty in Vault. "
                "Store token: docker compose exec vault vault kv put secret/github token=<token>",
                file=sys.stderr,
            )
            sys.exit(1)
        print("GitHub token loaded from Vault.")
        return token
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(
            f"BLOCKER: Vault lookup failed: {exc}. "
            "Ensure Vault is running: docker compose up -d vault",
            file=sys.stderr,
        )
        sys.exit(1)


def _github_get(path: str, token: str, params: dict[str, Any] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    req = Request(
        f"{GITHUB_API}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "handyman-rag-collector",
            "Authorization": f"Bearer {token}",
        },
    )
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            rate_remaining = exc.headers.get("X-RateLimit-Remaining")
            rate_reset = exc.headers.get("X-RateLimit-Reset")
            if exc.code in {403, 429} and rate_remaining == "0":
                raise RuntimeError(
                    "GitHub API rate limit reached. "
                    f"Reset epoch: {rate_reset or 'unknown'}."
                ) from exc
            raise RuntimeError(
                f"GitHub API error {exc.code} for {path}: {body}"
            ) from exc
        except URLError as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"GitHub API request failed for {path}: {exc}"
                ) from exc
            time.sleep(2**attempt)
    raise RuntimeError(f"GitHub API request failed after retries for {path}")


def _raw_get(url: str) -> str | None:
    """Fetch raw text from GitHub raw CDN. Returns None on 404 or network error."""
    req = Request(url, headers={"User-Agent": "handyman-rag-collector"})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code == 404:
            return None
        print(f"  WARNING: HTTP {exc.code} fetching {url}")
        return None
    except URLError as exc:
        print(f"  WARNING: URL error fetching {url}: {exc}")
        return None


def _load_split_ids(csv_path: Path) -> set[str]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["issue_number"].strip() for row in csv.DictReader(f)}


def _load_golden_ids(jsonl_path: Path) -> set[str]:
    if not jsonl_path.exists():
        return set()
    ids: set[str] = set()
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(str(json.loads(line)["issue_number"]).strip())
    return ids


def _load_heldout_candidates(path: Path) -> list[dict]:
    candidates: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    return candidates


def _select_issues(candidates: list[dict], max_issues: int) -> list[dict]:
    """Select up to max_issues candidates, preferring those with closed_at set."""
    with_closed = sorted(
        (c for c in candidates if c.get("closed_at")),
        key=lambda x: x.get("closed_at", ""),
        reverse=True,
    )
    without_closed = [c for c in candidates if not c.get("closed_at")]
    return (with_closed + without_closed)[:max_issues]


def _fetch_issue_comments(
    repo: str, issue_number: str, token: str, max_comments: int
) -> list[dict]:
    comments: list[dict] = []
    page = 1
    while len(comments) < max_comments:
        path = f"/repos/{repo}/issues/{issue_number}/comments"
        try:
            page_data = _github_get(path, token, {"per_page": 100, "page": page})
        except RuntimeError as exc:
            print(f"  WARNING: comment fetch failed for issue {issue_number}: {exc}")
            break
        if not page_data:
            break
        for c in page_data:
            if len(comments) >= max_comments:
                break
            assoc = c.get("author_association", "NONE")
            comments.append(
                {
                    "comment_id": c.get("id"),
                    "author_login": (c.get("user") or {}).get("login", ""),
                    "author_association": assoc,
                    "is_maintainer_like": assoc in MAINTAINER_LIKE_ASSOCIATIONS,
                    "created_at": c.get("created_at", ""),
                    "updated_at": c.get("updated_at", ""),
                    "body": c.get("body", ""),
                    "html_url": c.get("html_url", ""),
                }
            )
        if len(page_data) < 100:
            break
        page += 1
        time.sleep(_API_DELAY)
    return comments


def _collect_comments(
    selected: list[dict], repo: str, token: str, max_comments: int
) -> list[dict]:
    results: list[dict] = []
    for i, issue in enumerate(selected, 1):
        issue_num = issue["issue_number"]
        print(f"  [{i}/{len(selected)}] Fetching comments for issue #{issue_num}...")
        comments = _fetch_issue_comments(repo, issue_num, token, max_comments)
        results.append(
            {
                "issue_number": issue_num,
                "source_type": SOURCE_TYPE_ISSUE,
                "title": issue.get("title", ""),
                "body": issue.get("body", ""),
                "html_url": issue.get("html_url", ""),
                "raw_labels": issue.get("raw_labels", []),
                "created_at": issue.get("created_at", ""),
                "closed_at": issue.get("closed_at", ""),
                "comments": comments,
            }
        )
        print(f"    -> {len(comments)} comments")
        time.sleep(_API_DELAY)
    return results


def _collect_docs(
    candidates: list[tuple[str, str, str]],
    max_docs: int,
) -> tuple[list[dict], list[str]]:
    """Fetch bounded curated doc list from GitHub raw CDN.

    Args:
        candidates: list of (repo, branch, path) tuples to attempt in order
        max_docs: stop collecting after this many successful fetches

    Returns:
        (docs, failed_paths) where failed_paths are repo/path strings that returned None
    """
    docs: list[dict] = []
    failed: list[str] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    print(f"Attempting up to {max_docs} docs from {len(candidates)} candidate paths...")
    for repo, branch, doc_path in candidates:
        if len(docs) >= max_docs:
            print(f"  Reached max-docs={max_docs}, stopping doc collection.")
            break
        raw_url = f"{GITHUB_RAW_BASE}/{repo}/{branch}/{doc_path}"
        print(f"  [{repo}] {doc_path}...")
        text = _raw_get(raw_url)
        if text is None:
            print("    -> not found, skipping")
            failed.append(f"{repo}/{doc_path}")
            continue
        docs.append(
            {
                "source_type": SOURCE_TYPE_DOCS,
                "repo": repo,
                "path": doc_path,
                "title": Path(doc_path).name,
                "text": text,
                "source_url": f"{GITHUB_WEB_BASE}/{repo}/blob/{branch}/{doc_path}",
                "fetched_at": fetched_at,
            }
        )
        print(f"    -> collected ({len(text)} chars)")
    return docs, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect RAG corpus sources")
    parser.add_argument("--max-issues", type=int, default=50)
    parser.add_argument("--max-comments-per-issue", type=int, default=20)
    parser.add_argument("--repo", default="kubernetes/kubernetes")
    parser.add_argument(
        "--include-website-docs",
        type=lambda x: x.lower() not in {"false", "0", "no"},
        default=True,
        metavar="BOOL",
        help="Include kubernetes/website doc paths (default: true)",
    )
    parser.add_argument("--max-docs", type=int, default=12)
    args = parser.parse_args()

    t_start = time.time()

    if not RAG_HELDOUT_CANDIDATES_PATH.exists():
        print(
            f"ERROR: {RAG_HELDOUT_CANDIDATES_PATH} not found. "
            "Run RAG-1a first: python -m pipelines.rag.build_corpus",
            file=sys.stderr,
        )
        sys.exit(1)

    token = _get_github_token()

    print("Loading classifier split IDs for leakage re-check...")
    train_ids = _load_split_ids(OFFICIAL_TRAIN_PATH)
    val_ids = _load_split_ids(OFFICIAL_VAL_PATH)
    test_ids = _load_split_ids(OFFICIAL_TEST_PATH)
    golden_ids = _load_golden_ids(CLASSIFICATION_GOLDEN_PATH)
    print(
        f"  train={len(train_ids)}  val={len(val_ids)}  "
        f"test={len(test_ids)}  golden={len(golden_ids)}"
    )

    print("Loading held-out issue candidates...")
    candidates = _load_heldout_candidates(RAG_HELDOUT_CANDIDATES_PATH)
    print(f"  heldout_issues_available={len(candidates)}")

    print(f"Selecting up to {args.max_issues} issues (prefer closed)...")
    selected = _select_issues(candidates, args.max_issues)
    print(f"  selected={len(selected)}")

    selected_ids = {s["issue_number"] for s in selected}
    overlap_train = len(selected_ids & train_ids)
    overlap_val = len(selected_ids & val_ids)
    overlap_test = len(selected_ids & test_ids)
    overlap_golden = len(selected_ids & golden_ids)
    leakage_recheck_passed = (
        overlap_train == 0
        and overlap_val == 0
        and overlap_test == 0
        and overlap_golden == 0
    )
    if not leakage_recheck_passed:
        print(
            "ERROR: Leakage detected in selected issues! "
            f"train={overlap_train} val={overlap_val} "
            f"test={overlap_test} golden={overlap_golden}",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Leakage re-check PASSED.")

    print(f"\nCollecting comments (max {args.max_comments_per_issue} per issue)...")
    issues_with_comments = _collect_comments(
        selected, args.repo, token, args.max_comments_per_issue
    )
    issues_with_comments_count = sum(1 for r in issues_with_comments if r["comments"])
    total_comments = sum(len(r["comments"]) for r in issues_with_comments)
    maintainer_like_count = sum(
        1
        for r in issues_with_comments
        for c in r["comments"]
        if c["is_maintainer_like"]
    )

    RAG_ISSUES_WITH_COMMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_ISSUES_WITH_COMMENTS_PATH.open("w", encoding="utf-8", newline="") as f:
        for record in issues_with_comments:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(
        f"Wrote {len(issues_with_comments)} issue records -> {RAG_ISSUES_WITH_COMMENTS_PATH}"
    )
    print(
        f"  issues_with_comments={issues_with_comments_count}  "
        f"total_comments={total_comments}  "
        f"maintainer_like={maintainer_like_count}"
    )

    # Build doc candidate list based on flags
    doc_candidates: list[tuple[str, str, str]] = [
        (repo, branch, path)
        for repo, branch, path in DOC_SOURCES
        if repo == "kubernetes/kubernetes" or args.include_website_docs
    ]

    print(
        f"\nCollecting docs (max-docs={args.max_docs}, candidates={len(doc_candidates)})..."
    )
    docs, failed_doc_paths = _collect_docs(doc_candidates, args.max_docs)
    docs_repos_used = sorted({d["repo"] for d in docs})
    print(f"  docs_collected={len(docs)}  failed={len(failed_doc_paths)}")
    print(f"  repos_used={docs_repos_used}")

    RAG_DOC_SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_DOC_SOURCES_PATH.open("w", encoding="utf-8", newline="") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"Wrote {len(docs)} doc records -> {RAG_DOC_SOURCES_PATH}")

    if not docs:
        print(
            "WARNING: No docs collected from candidate paths. "
            "Manual doc source selection required before chunking."
        )

    elapsed = round(time.time() - t_start, 1)

    report = {
        "docs_attempted_count": len(doc_candidates),
        "docs_collected_count": len(docs),
        "docs_repos_used": docs_repos_used,
        "failed_doc_paths": failed_doc_paths,
        "heldout_issues_available": len(candidates),
        "issues_selected_count": len(selected),
        "issues_with_comments_count": issues_with_comments_count,
        "total_comments_collected": total_comments,
        "maintainer_like_comments_count": maintainer_like_count,
        "leakage_recheck_passed": leakage_recheck_passed,
        "overlap_with_train": overlap_train,
        "overlap_with_val": overlap_val,
        "overlap_with_test": overlap_test,
        "overlap_with_classification_golden": overlap_golden,
        "elapsed_seconds": elapsed,
    }
    RAG_CORPUS_COLLECTION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_CORPUS_COLLECTION_REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote corpus collection report -> {RAG_CORPUS_COLLECTION_REPORT_PATH}")

    docs_status = "collected" if docs else "pending_no_docs_found"
    comments_status = "collected" if issues_with_comments_count > 0 else "pending"
    corpus_status = (
        "sources_collected"
        if docs and issues_with_comments_count > 0
        else "sources_collected_partial"
    )

    manifest = {
        "status": corpus_status,
        "docs_status": docs_status,
        "comments_status": comments_status,
        "issue_candidates_path": str(RAG_HELDOUT_CANDIDATES_PATH),
        "issues_with_comments_path": str(RAG_ISSUES_WITH_COMMENTS_PATH),
        "docs_path": str(RAG_DOC_SOURCES_PATH),
        "collection_report_path": str(RAG_CORPUS_COLLECTION_REPORT_PATH),
        "leakage_report_path": str(RAG_LEAKAGE_REPORT_PATH),
        "source_policy": (
            "RAG issue corpus must not include classifier train/val/test issues."
        ),
    }
    RAG_CORPUS_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_CORPUS_MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Updated corpus manifest -> {RAG_CORPUS_MANIFEST_PATH}")

    print(f"\nDONE - RAG-1c corpus source collection complete. elapsed={elapsed}s")

    if not docs:
        print(
            "\nBLOCKER: No docs collected. "
            "Manual doc source selection required before chunking can proceed."
        )


if __name__ == "__main__":
    main()
