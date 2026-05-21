"""RAG-3a: Generate RAG golden set candidates from section-aware chunks."""

import argparse
import csv
import json
import re
from pathlib import Path

from app.services.rag.config import (
    RAG_CHUNKS_SECTION_PATH,
    RAG_GOLDEN_CANDIDATES_PATH,
    RAG_GOLDEN_CANDIDATES_SUMMARY_PATH,
    RAG_GOLDEN_DIR,
    SOURCE_TYPE_COMMENT,
    SOURCE_TYPE_DOCS,
    SOURCE_TYPE_ISSUE,
)

_IDEAL_ANSWER_MAX_CHARS = 300
_MAX_DOCS_CANDIDATES = 12
_MAX_ISSUE_CANDIDATES = 20
_MAX_COMMENT_CANDIDATES = 15
_MIN_CONTENT_CHARS = 80  # minimum chunk length to be a useful candidate

_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_LINK_RE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")  # badge images
_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_SEPARATOR_RE = re.compile(r"^[-*_]{3,}$", re.MULTILINE)
_BOT_CMD_RE = re.compile(r"^/\S+", re.MULTILINE)

_METADATA_SECTION_KEYWORDS = frozenset(
    {
        "kubernetes version",
        "cloud provider",
        "os version",
        "install tools",
        "container runtime",
        "related plugins",
    }
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RAG golden set candidates from section-aware chunks."
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _clean_section_label(section: str | None) -> str:
    if not section:
        return ""
    return _HEADING_RE.sub("", section).strip().rstrip("?").strip()


def _is_metadata_section(section: str | None) -> bool:
    if not section:
        return False
    lower = section.lower()
    return any(kw in lower for kw in _METADATA_SECTION_KEYWORDS)


def _extract_ideal_answer(text: str, section: str | None, max_chars: int) -> str:
    """Return a short extractive answer grounded in the chunk text."""
    body = text
    # Strip leading section heading
    if section and body.startswith(section):
        body = body[len(section) :].strip()
    # Remove badge/image links
    body = _LINK_RE.sub("", body)
    # Inline links -> display text only
    body = _INLINE_LINK_RE.sub(r"\1", body)
    # Strip markdown headings
    body = _HEADING_RE.sub("", body)
    # Strip horizontal rules
    body = _SEPARATOR_RE.sub("", body)
    # Skip bot command lines (/assign, /triage, etc.)
    body = _BOT_CMD_RE.sub("", body)
    # Collapse whitespace
    body = re.sub(r"\n{2,}", " ", body).strip()
    body = re.sub(r"[ \t]+", " ", body).strip()

    if not body:
        return text[:max_chars].strip()
    if len(body) <= max_chars:
        return body
    truncated = body[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars // 2:
        return truncated[: last_period + 1]
    return truncated.rstrip() + "..."


# ---------------------------------------------------------------------------
# Question generators
# ---------------------------------------------------------------------------


def _question_docs(chunk: dict) -> str:
    sl = _clean_section_label(chunk.get("section"))
    title = chunk.get("title", "document")
    if sl:
        return f"What does the Kubernetes documentation say about {sl}?"
    return f"What does the {title} document cover?"


def _question_issue(chunk: dict) -> str:
    num = chunk.get("issue_number") or "unknown"
    title = chunk.get("title") or ""
    sl = (chunk.get("section") or "").lower()
    short_title = title[:60] + ("..." if len(title) > 60 else "")

    if "what happened" in sl:
        return f"What problem was reported in issue #{num}: {short_title}?"
    if "expect" in sl:
        return f"What was the expected behavior described in issue #{num}?"
    if "reproduc" in sl:
        return f"How can the issue in #{num} be reproduced?"
    return f"What was the reported issue in #{num}: {short_title}?"


def _question_comment(chunk: dict) -> str:
    num = chunk.get("issue_number") or "unknown"
    title = chunk.get("title") or ""
    short_title = title[:50] + ("..." if len(title) > 50 else "")
    return f"What resolution or maintainer guidance was provided for issue #{num} ({short_title})?"


# ---------------------------------------------------------------------------
# Notes generator
# ---------------------------------------------------------------------------


def _make_notes(chunk: dict) -> str:
    st = chunk.get("source_type", "")
    if st == SOURCE_TYPE_DOCS:
        return (
            f"From docs: {chunk.get('title', '')} | "
            f"section: {chunk.get('section', 'n/a')} | "
            f"char_length: {chunk.get('char_length', 0)}"
        )
    if st == SOURCE_TYPE_ISSUE:
        labels = ", ".join(chunk.get("raw_labels") or []) or "none"
        return (
            f"Issue #{chunk.get('issue_number')} | "
            f"labels: {labels} | "
            f"section: {chunk.get('section', 'n/a')} | "
            f"char_length: {chunk.get('char_length', 0)}"
        )
    if st == SOURCE_TYPE_COMMENT:
        return (
            f"Comment by {chunk.get('author_login', 'unknown')} "
            f"({chunk.get('author_association', '?')}) "
            f"on issue #{chunk.get('issue_number')} | "
            f"maintainer_like: {chunk.get('is_maintainer_like', False)} | "
            f"char_length: {chunk.get('char_length', 0)}"
        )
    return f"source_type={st}"


# ---------------------------------------------------------------------------
# Candidate selectors (deterministic — sort by chunk_id before selection)
# ---------------------------------------------------------------------------


def _select_docs_candidates(chunks: list[dict], max_count: int) -> list[dict]:
    eligible = [
        c
        for c in chunks
        if c["source_type"] == SOURCE_TYPE_DOCS
        and c["char_length"] >= _MIN_CONTENT_CHARS
        and c.get("section")
    ]
    # Group by doc (source_record_id) for cross-doc diversity
    by_doc: dict[str, list[dict]] = {}
    for c in eligible:
        by_doc.setdefault(c["source_record_id"], []).append(c)

    selected: list[dict] = []
    per_doc = max(1, max_count // max(1, len(by_doc)))

    for doc_id in sorted(by_doc.keys()):
        doc_chunks = sorted(by_doc[doc_id], key=lambda c: c["chunk_id"])
        step = max(1, len(doc_chunks) // per_doc)
        selected.extend(doc_chunks[::step][:per_doc])

    return sorted(selected, key=lambda c: c["chunk_id"])[:max_count]


def _select_issue_candidates(chunks: list[dict], max_count: int) -> list[dict]:
    """One chunk per issue; prefer 'What happened?' sections."""
    by_issue: dict[str, list[dict]] = {}
    for c in chunks:
        if (
            c["source_type"] == SOURCE_TYPE_ISSUE
            and c["char_length"] >= _MIN_CONTENT_CHARS
            and not _is_metadata_section(c.get("section"))
        ):
            by_issue.setdefault(c["issue_number"], []).append(c)

    selected: list[dict] = []
    for num in sorted(by_issue.keys()):
        issue_chunks = by_issue[num]
        # Prefer "What happened?" section
        best = None
        for c in issue_chunks:
            sl = (c.get("section") or "").lower()
            if "what happened" in sl:
                best = c
                break
        if best is None:
            # Fallback: longest chunk
            best = max(issue_chunks, key=lambda c: c["char_length"])
        selected.append(best)
        if len(selected) >= max_count:
            break

    return selected


def _select_comment_candidates(chunks: list[dict], max_count: int) -> list[dict]:
    """One maintainer-like comment chunk per issue; prefer longest answer."""
    by_issue: dict[str, list[dict]] = {}
    for c in chunks:
        if (
            c["source_type"] == SOURCE_TYPE_COMMENT
            and c.get("is_maintainer_like")
            and c["char_length"] >= _MIN_CONTENT_CHARS
        ):
            by_issue.setdefault(c["issue_number"], []).append(c)

    selected: list[dict] = []
    for num in sorted(by_issue.keys()):
        best = max(by_issue[num], key=lambda c: c["char_length"])
        selected.append(best)
        if len(selected) >= max_count:
            break

    return selected


# ---------------------------------------------------------------------------
# Candidate builder
# ---------------------------------------------------------------------------


def _build_candidate(
    cand_id: str, chunk: dict, question: str, answer: str, notes: str
) -> dict:
    return {
        "candidate_id": cand_id,
        "question": question,
        "ideal_answer": answer,
        "ground_truth_chunk_ids": chunk["chunk_id"],
        "source_urls": chunk.get("source_url", ""),
        "source_types": chunk["source_type"],
        "issue_numbers": chunk.get("issue_number") or "",
        "notes": notes,
        "hand_labeled_for_judge_check": "false",
        "curator_status": "candidate",
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate(candidates: list[dict], valid_ids: set[str]) -> tuple[bool, list[str]]:
    invalid: list[str] = []
    for c in candidates:
        for cid in c["ground_truth_chunk_ids"].split(";"):
            cid = cid.strip()
            if cid and cid not in valid_ids:
                invalid.append(cid)
    return len(invalid) == 0, invalid


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _parse_args()

    print("RAG-3a: Loading section-aware chunks...")
    chunks = _load_jsonl(RAG_CHUNKS_SECTION_PATH)
    valid_ids = {c["chunk_id"] for c in chunks}
    print(f"  loaded {len(chunks)} chunks")

    docs_sel = _select_docs_candidates(chunks, _MAX_DOCS_CANDIDATES)
    issue_sel = _select_issue_candidates(chunks, _MAX_ISSUE_CANDIDATES)
    comment_sel = _select_comment_candidates(chunks, _MAX_COMMENT_CANDIDATES)
    print(
        f"  selected: docs={len(docs_sel)}, issues={len(issue_sel)}, "
        f"comments={len(comment_sel)}"
    )

    all_candidates: list[dict] = []
    idx = 0

    for chunk in docs_sel:
        q = _question_docs(chunk)
        a = _extract_ideal_answer(
            chunk["text"], chunk.get("section"), _IDEAL_ANSWER_MAX_CHARS
        )
        all_candidates.append(
            _build_candidate(f"cand_{idx:04d}", chunk, q, a, _make_notes(chunk))
        )
        idx += 1

    for chunk in issue_sel:
        q = _question_issue(chunk)
        a = _extract_ideal_answer(
            chunk["text"], chunk.get("section"), _IDEAL_ANSWER_MAX_CHARS
        )
        all_candidates.append(
            _build_candidate(f"cand_{idx:04d}", chunk, q, a, _make_notes(chunk))
        )
        idx += 1

    for chunk in comment_sel:
        q = _question_comment(chunk)
        a = _extract_ideal_answer(
            chunk["text"], chunk.get("section"), _IDEAL_ANSWER_MAX_CHARS
        )
        all_candidates.append(
            _build_candidate(f"cand_{idx:04d}", chunk, q, a, _make_notes(chunk))
        )
        idx += 1

    passed, invalid_refs = _validate(all_candidates, valid_ids)
    print(f"  total_candidates={len(all_candidates)}, validation_passed={passed}")
    if invalid_refs:
        print(f"  INVALID refs: {invalid_refs}")

    # Write CSV
    RAG_GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "candidate_id",
        "question",
        "ideal_answer",
        "ground_truth_chunk_ids",
        "source_urls",
        "source_types",
        "issue_numbers",
        "notes",
        "hand_labeled_for_judge_check",
        "curator_status",
    ]
    with open(RAG_GOLDEN_CANDIDATES_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_candidates)
    print(f"  wrote {RAG_GOLDEN_CANDIDATES_PATH}")

    # Write summary JSON
    counts_by_type: dict[str, int] = {}
    for c in all_candidates:
        st = c["source_types"]
        counts_by_type[st] = counts_by_type.get(st, 0) + 1

    unique_chunks = {
        cid.strip()
        for c in all_candidates
        for cid in c["ground_truth_chunk_ids"].split(";")
        if cid.strip()
    }

    summary = {
        "total_candidates": len(all_candidates),
        "candidate_counts_by_source_type": counts_by_type,
        "maintainer_like_candidate_count": counts_by_type.get(SOURCE_TYPE_COMMENT, 0),
        "unique_ground_truth_chunks": len(unique_chunks),
        "invalid_ground_truth_chunk_refs": invalid_refs,
        "validation_passed": passed,
        "output_csv": str(RAG_GOLDEN_CANDIDATES_PATH),
        "source_chunks_path": str(RAG_CHUNKS_SECTION_PATH),
    }
    with open(RAG_GOLDEN_CANDIDATES_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  wrote {RAG_GOLDEN_CANDIDATES_SUMMARY_PATH}")
    print("RAG-3a complete.")


if __name__ == "__main__":
    main()
