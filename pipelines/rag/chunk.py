"""RAG-2: Chunking experiments — baseline fixed-size and section-aware."""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.services.rag.config import (  # noqa: E402
    BASELINE_FIXED_CHUNK_CHARS,
    CHUNK_OVERLAP_CHARS,
    MIN_CHUNK_CHARS,
    RAG_CHUNKS_BASELINE_PATH,
    RAG_CHUNKS_DIR,
    RAG_CHUNKS_SECTION_PATH,
    RAG_CHUNKING_EXAMPLES_PATH,
    RAG_CHUNKING_REPORT_PATH,
    RAG_DOC_SOURCES_PATH,
    RAG_ISSUES_WITH_COMMENTS_PATH,
    RAG_REPORTS_DIR,
    SECTION_AWARE_MAX_CHARS,
    SOURCE_TYPE_COMMENT,
    SOURCE_TYPE_DOCS,
    SOURCE_TYPE_ISSUE,
    STRATEGY_BASELINE_FIXED,
    STRATEGY_SECTION_AWARE,
    TINY_CHUNK_HIGH_SIGNAL_TOKENS,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+.+$", re.MULTILINE)
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")
_EXAMPLES_PER_SOURCE_TYPE = 2
_TEXT_PREVIEW_CHARS = 200

_TINY_CHUNK_POLICY = (
    f"Drop chunks where cleaned text length < {MIN_CHUNK_CHARS} chars, "
    "unless the text contains at least one high-signal Kubernetes technical token "
    f"({', '.join(sorted(TINY_CHUNK_HIGH_SIGNAL_TOKENS))}). "
    "Matched case-insensitively as substrings."
)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:80]


def _make_chunk_id(strategy: str, source_type: str, source_id: str, idx: int) -> str:
    return f"{strategy}__{source_type}__{source_id}__{idx:04d}"


# ---------------------------------------------------------------------------
# Quality filter
# ---------------------------------------------------------------------------


def _clean_text(text: str) -> str:
    text = text.strip()
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)
    return text


def _is_high_signal(text: str) -> bool:
    lower = text.lower()
    return any(tok in lower for tok in TINY_CHUNK_HIGH_SIGNAL_TOKENS)


def _apply_quality_filter(chunks: list[dict], min_chars: int) -> tuple[list[dict], int]:
    """Return (kept_chunks, dropped_count). Cleans text and char_length in kept chunks."""
    kept = []
    dropped = 0
    for c in chunks:
        cleaned = _clean_text(c["text"])
        if len(cleaned) >= min_chars or _is_high_signal(cleaned):
            c["text"] = cleaned
            c["char_length"] = len(cleaned)
            kept.append(c)
        else:
            dropped += 1
    return kept, dropped


# ---------------------------------------------------------------------------
# Splitting helpers
# ---------------------------------------------------------------------------


def _chunk_fixed(text: str, chunk_chars: int, overlap_chars: int) -> Iterator[str]:
    """Yield fixed-size character chunks with overlap."""
    if not text.strip():
        return
    start = 0
    while start < len(text):
        end = start + chunk_chars
        yield text[start:end]
        if end >= len(text):
            break
        start = end - overlap_chars


def _split_by_paragraphs(
    heading: str, text: str, max_chars: int
) -> Iterator[tuple[str, str]]:
    """
    Yield (heading, chunk_text) by accumulating paragraphs up to max_chars.
    Falls back to hard character split for single paragraphs that exceed max_chars.
    """
    if not text.strip():
        return
    paragraphs = re.split(r"\n\n+", text)
    buffer = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = (buffer + "\n\n" + para).strip() if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            if buffer:
                yield heading, buffer
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars):
                    yield heading, para[i : i + max_chars]
                buffer = ""
            else:
                buffer = para
    if buffer:
        yield heading, buffer


def _split_markdown_sections(text: str, max_chars: int) -> Iterator[tuple[str, str]]:
    """
    Yield (heading, section_text) by splitting on markdown headings.
    Text before the first heading is yielded as a preamble with heading="".
    Sections that exceed max_chars are split further by paragraph boundaries.
    """
    if not text.strip():
        return
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        yield from _split_by_paragraphs("", text, max_chars)
        return

    preamble = text[: matches[0].start()].strip()
    if preamble:
        yield from _split_by_paragraphs("", preamble, max_chars)

    for i, match in enumerate(matches):
        heading = match.group(0).strip()
        section_start = match.end()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_body = text[section_start:section_end].strip()
        full = (heading + "\n\n" + section_body).strip() if section_body else heading
        if len(full) <= max_chars:
            yield heading, full
        else:
            yield from _split_by_paragraphs(heading, full, max_chars)


# ---------------------------------------------------------------------------
# Chunk builder
# ---------------------------------------------------------------------------


def _build_chunk(
    *,
    strategy: str,
    source_type: str,
    source_url: str,
    title: str,
    section: str | None,
    issue_number: str | None,
    raw_labels: list | None,
    created_at: str | None,
    closed_at: str | None,
    author_login: str | None,
    author_association: str | None,
    is_maintainer_like: bool | None,
    text: str,
    source_record_id: str,
    chunk_idx: int,
) -> dict:
    return {
        "chunk_id": _make_chunk_id(strategy, source_type, source_record_id, chunk_idx),
        "strategy": strategy,
        "source_type": source_type,
        "source_url": source_url,
        "title": title,
        "section": section,
        "issue_number": issue_number,
        "raw_labels": raw_labels,
        "created_at": created_at,
        "closed_at": closed_at,
        "author_login": author_login,
        "author_association": author_association,
        "is_maintainer_like": is_maintainer_like,
        "text": text,
        "char_length": len(text),
        "source_record_id": source_record_id,
    }


# ---------------------------------------------------------------------------
# Baseline fixed-size chunkers
# ---------------------------------------------------------------------------


def _baseline_chunks_doc(doc: dict) -> list[dict]:
    text = doc.get("text") or ""
    if not text.strip():
        return []
    source_id = _slug(f"{doc.get('repo', '')}_{doc.get('path', '')}")
    return [
        _build_chunk(
            strategy=STRATEGY_BASELINE_FIXED,
            source_type=SOURCE_TYPE_DOCS,
            source_url=doc.get("source_url", ""),
            title=doc.get("title", ""),
            section=None,
            issue_number=None,
            raw_labels=None,
            created_at=doc.get("fetched_at"),
            closed_at=None,
            author_login=None,
            author_association=None,
            is_maintainer_like=None,
            text=chunk_text,
            source_record_id=source_id,
            chunk_idx=idx,
        )
        for idx, chunk_text in enumerate(
            _chunk_fixed(text, BASELINE_FIXED_CHUNK_CHARS, CHUNK_OVERLAP_CHARS)
        )
    ]


def _baseline_chunks_issue(issue: dict) -> list[dict]:
    title = issue.get("title", "")
    body = issue.get("body") or ""
    text = (title + "\n\n" + body).strip()
    if not text:
        return []
    source_id = f"issue_{issue['issue_number']}"
    return [
        _build_chunk(
            strategy=STRATEGY_BASELINE_FIXED,
            source_type=SOURCE_TYPE_ISSUE,
            source_url=issue.get("html_url", ""),
            title=title,
            section=None,
            issue_number=str(issue["issue_number"]),
            raw_labels=issue.get("raw_labels"),
            created_at=issue.get("created_at"),
            closed_at=issue.get("closed_at"),
            author_login=None,
            author_association=None,
            is_maintainer_like=None,
            text=chunk_text,
            source_record_id=source_id,
            chunk_idx=idx,
        )
        for idx, chunk_text in enumerate(
            _chunk_fixed(text, BASELINE_FIXED_CHUNK_CHARS, CHUNK_OVERLAP_CHARS)
        )
    ]


def _baseline_chunks_comment(comment: dict, issue: dict) -> list[dict]:
    text = comment.get("body") or ""
    if not text.strip():
        return []
    source_id = f"comment_{comment['comment_id']}"
    return [
        _build_chunk(
            strategy=STRATEGY_BASELINE_FIXED,
            source_type=SOURCE_TYPE_COMMENT,
            source_url=comment.get("html_url", ""),
            title=issue.get("title", ""),
            section=None,
            issue_number=str(issue["issue_number"]),
            raw_labels=issue.get("raw_labels"),
            created_at=comment.get("created_at"),
            closed_at=None,
            author_login=comment.get("author_login"),
            author_association=comment.get("author_association"),
            is_maintainer_like=comment.get("is_maintainer_like"),
            text=chunk_text,
            source_record_id=source_id,
            chunk_idx=idx,
        )
        for idx, chunk_text in enumerate(
            _chunk_fixed(text, BASELINE_FIXED_CHUNK_CHARS, CHUNK_OVERLAP_CHARS)
        )
    ]


# ---------------------------------------------------------------------------
# Section-aware chunkers
# ---------------------------------------------------------------------------


def _section_chunks_doc(doc: dict) -> list[dict]:
    text = doc.get("text") or ""
    if not text.strip():
        return []
    source_id = _slug(f"{doc.get('repo', '')}_{doc.get('path', '')}")
    chunks = []
    for idx, (heading, section_text) in enumerate(
        _split_markdown_sections(text, SECTION_AWARE_MAX_CHARS)
    ):
        if not section_text.strip():
            continue
        chunks.append(
            _build_chunk(
                strategy=STRATEGY_SECTION_AWARE,
                source_type=SOURCE_TYPE_DOCS,
                source_url=doc.get("source_url", ""),
                title=doc.get("title", ""),
                section=heading or None,
                issue_number=None,
                raw_labels=None,
                created_at=doc.get("fetched_at"),
                closed_at=None,
                author_login=None,
                author_association=None,
                is_maintainer_like=None,
                text=section_text,
                source_record_id=source_id,
                chunk_idx=idx,
            )
        )
    return chunks


def _section_chunks_issue(issue: dict) -> list[dict]:
    title = issue.get("title", "")
    body = issue.get("body") or ""
    text = (title + "\n\n" + body).strip()
    if not text:
        return []
    source_id = f"issue_{issue['issue_number']}"
    chunks = []
    for idx, (heading, section_text) in enumerate(
        _split_markdown_sections(text, SECTION_AWARE_MAX_CHARS)
    ):
        if not section_text.strip():
            continue
        chunks.append(
            _build_chunk(
                strategy=STRATEGY_SECTION_AWARE,
                source_type=SOURCE_TYPE_ISSUE,
                source_url=issue.get("html_url", ""),
                title=title,
                section=heading or None,
                issue_number=str(issue["issue_number"]),
                raw_labels=issue.get("raw_labels"),
                created_at=issue.get("created_at"),
                closed_at=issue.get("closed_at"),
                author_login=None,
                author_association=None,
                is_maintainer_like=None,
                text=section_text,
                source_record_id=source_id,
                chunk_idx=idx,
            )
        )
    return chunks


def _section_chunks_comment(comment: dict, issue: dict) -> list[dict]:
    text = comment.get("body") or ""
    if not text.strip():
        return []
    source_id = f"comment_{comment['comment_id']}"
    chunks = []
    idx = 0
    for _, chunk_text in _split_by_paragraphs("", text, SECTION_AWARE_MAX_CHARS):
        if not chunk_text.strip():
            continue
        chunks.append(
            _build_chunk(
                strategy=STRATEGY_SECTION_AWARE,
                source_type=SOURCE_TYPE_COMMENT,
                source_url=comment.get("html_url", ""),
                title=issue.get("title", ""),
                section=None,
                issue_number=str(issue["issue_number"]),
                raw_labels=issue.get("raw_labels"),
                created_at=comment.get("created_at"),
                closed_at=None,
                author_login=comment.get("author_login"),
                author_association=comment.get("author_association"),
                is_maintainer_like=comment.get("is_maintainer_like"),
                text=chunk_text,
                source_record_id=source_id,
                chunk_idx=idx,
            )
        )
        idx += 1
    return chunks


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def _stats(chunks: list[dict]) -> dict:
    if not chunks:
        return {
            "count": 0,
            "avg_char_length": 0,
            "min_char_length": 0,
            "max_char_length": 0,
        }
    lengths = [c["char_length"] for c in chunks]
    return {
        "count": len(chunks),
        "avg_char_length": round(sum(lengths) / len(lengths), 1),
        "min_char_length": min(lengths),
        "max_char_length": max(lengths),
    }


def _counts_by_source_type(chunks: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for c in chunks:
        st = c["source_type"]
        counts[st] = counts.get(st, 0) + 1
    return counts


def _collect_examples(chunks: list[dict], n_per_type: int) -> list[dict]:
    seen: dict[str, int] = {}
    out = []
    for c in chunks:
        st = c["source_type"]
        if seen.get(st, 0) < n_per_type:
            out.append(c)
            seen[st] = seen.get(st, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("RAG-2: Loading corpus sources...")
    docs = _load_jsonl(RAG_DOC_SOURCES_PATH)
    issues = _load_jsonl(RAG_ISSUES_WITH_COMMENTS_PATH)
    total_comments = sum(len(issue.get("comments", [])) for issue in issues)
    print(f"  docs={len(docs)}, issues={len(issues)}, comments={total_comments}")

    # --- Baseline ---
    print("Building baseline_fixed chunks...")
    baseline_raw: list[dict] = []
    for doc in docs:
        baseline_raw.extend(_baseline_chunks_doc(doc))
    for issue in issues:
        baseline_raw.extend(_baseline_chunks_issue(issue))
        for comment in issue.get("comments", []):
            baseline_raw.extend(_baseline_chunks_comment(comment, issue))

    # --- Section-aware ---
    print("Building section_aware chunks...")
    section_raw: list[dict] = []
    for doc in docs:
        section_raw.extend(_section_chunks_doc(doc))
    for issue in issues:
        section_raw.extend(_section_chunks_issue(issue))
        for comment in issue.get("comments", []):
            section_raw.extend(_section_chunks_comment(comment, issue))

    # --- Quality filter ---
    print(f"Applying quality filter (min_chars={MIN_CHUNK_CHARS})...")
    baseline, b_dropped = _apply_quality_filter(baseline_raw, MIN_CHUNK_CHARS)
    section, s_dropped = _apply_quality_filter(section_raw, MIN_CHUNK_CHARS)
    print(
        f"  baseline: {len(baseline_raw)} -> {len(baseline)} kept, {b_dropped} dropped"
    )
    print(
        f"  section_aware: {len(section_raw)} -> {len(section)} kept, {s_dropped} dropped"
    )

    # --- Write JSONL ---
    RAG_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    _write_jsonl(RAG_CHUNKS_BASELINE_PATH, baseline)
    _write_jsonl(RAG_CHUNKS_SECTION_PATH, section)
    print(f"  wrote {RAG_CHUNKS_BASELINE_PATH}")
    print(f"  wrote {RAG_CHUNKS_SECTION_PATH}")

    # --- Report ---
    b_stats = _stats(baseline)
    s_stats = _stats(section)
    b_maintainer = sum(
        1
        for c in baseline
        if c["source_type"] == SOURCE_TYPE_COMMENT and c.get("is_maintainer_like")
    )
    s_maintainer = sum(
        1
        for c in section
        if c["source_type"] == SOURCE_TYPE_COMMENT and c.get("is_maintainer_like")
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_docs_count": len(docs),
        "input_issues_count": len(issues),
        "total_comments_seen": total_comments,
        "min_chunk_chars": MIN_CHUNK_CHARS,
        "tiny_chunk_policy": _TINY_CHUNK_POLICY,
        "baseline_chunk_count": b_stats["count"],
        "baseline_dropped_tiny_chunks": b_dropped,
        "baseline_counts_by_source_type": _counts_by_source_type(baseline),
        "baseline_avg_char_length": b_stats["avg_char_length"],
        "baseline_min_char_length_after_filter": b_stats["min_char_length"],
        "baseline_max_char_length": b_stats["max_char_length"],
        "baseline_maintainer_like_comment_chunks": b_maintainer,
        "section_aware_chunk_count": s_stats["count"],
        "section_aware_dropped_tiny_chunks": s_dropped,
        "section_aware_counts_by_source_type": _counts_by_source_type(section),
        "section_aware_avg_char_length": s_stats["avg_char_length"],
        "section_aware_min_char_length_after_filter": s_stats["min_char_length"],
        "section_aware_max_char_length": s_stats["max_char_length"],
        "section_aware_maintainer_like_comment_chunks": s_maintainer,
        "examples_path": str(RAG_CHUNKING_EXAMPLES_PATH),
        "chosen_for_next_phase": STRATEGY_SECTION_AWARE,
        "rationale": (
            "Section-aware preserves document headings, issue template sections, "
            "and comment/maintainer metadata better than naive fixed-size chunks. "
            "Each chunk corresponds to a semantically coherent unit (a doc section, "
            "an issue template field, or a single comment thread) rather than an "
            "arbitrary character boundary."
        ),
    }

    RAG_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAG_CHUNKING_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  wrote {RAG_CHUNKING_REPORT_PATH}")

    # --- Examples CSV ---
    fieldnames = [
        "strategy",
        "source_type",
        "issue_number_or_path",
        "title",
        "section",
        "char_length",
        "text_preview",
    ]
    examples = _collect_examples(
        baseline, _EXAMPLES_PER_SOURCE_TYPE
    ) + _collect_examples(section, _EXAMPLES_PER_SOURCE_TYPE)
    with open(RAG_CHUNKING_EXAMPLES_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in examples:
            path_or_num = c.get("issue_number") or c.get("source_record_id", "")
            writer.writerow(
                {
                    "strategy": c["strategy"],
                    "source_type": c["source_type"],
                    "issue_number_or_path": path_or_num,
                    "title": c.get("title", ""),
                    "section": c.get("section") or "",
                    "char_length": c["char_length"],
                    "text_preview": c["text"][:_TEXT_PREVIEW_CHARS].replace("\n", " "),
                }
            )
    print(f"  wrote {RAG_CHUNKING_EXAMPLES_PATH}")
    print("RAG-2b complete.")


if __name__ == "__main__":
    main()
