"""Centralized constants for the Advanced RAG service and offline experiments."""

from app.core.paths import RAG_DATA_DIR, RAG_GOLDEN_DIR, RAG_REPORTS_DIR

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAG_RAW_DOCS_DIR = RAG_DATA_DIR / "raw_docs"
RAG_PROCESSED_DIR = RAG_DATA_DIR / "processed"
RAG_CHUNKS_DIR = RAG_DATA_DIR / "chunks"

RAG_FIGURES_DIR = RAG_REPORTS_DIR / "figures"

RAG_GOLDEN_CANDIDATES_PATH = RAG_GOLDEN_DIR / "rag_golden_candidates.csv"
RAG_GOLDEN_CANDIDATES_SUMMARY_PATH = (
    RAG_GOLDEN_DIR / "rag_golden_candidates_summary.json"
)
RAG_GOLDEN_REVIEW_CSV_PATH = RAG_GOLDEN_DIR / "rag_golden_candidates_review.csv"
RAG_GOLDEN_REVIEW_SUMMARY_PATH = RAG_GOLDEN_DIR / "rag_golden_review_summary.json"
RAG_GOLDEN_PATH = RAG_GOLDEN_DIR / "rag_golden.jsonl"
RAG_GOLDEN_SUMMARY_PATH = RAG_GOLDEN_DIR / "rag_golden_summary.json"

RAG_HELDOUT_CANDIDATES_PATH = RAG_PROCESSED_DIR / "heldout_issue_candidates.jsonl"
RAG_ISSUES_WITH_COMMENTS_PATH = RAG_PROCESSED_DIR / "issues_with_comments.jsonl"
RAG_DOC_SOURCES_PATH = RAG_RAW_DOCS_DIR / "doc_sources.jsonl"
RAG_CORPUS_MANIFEST_PATH = RAG_DATA_DIR / "corpus_manifest.json"
RAG_LEAKAGE_REPORT_PATH = RAG_REPORTS_DIR / "leakage_report.json"
RAG_CORPUS_COLLECTION_REPORT_PATH = RAG_REPORTS_DIR / "corpus_collection_report.json"
RAG_CHUNKS_BASELINE_PATH = RAG_CHUNKS_DIR / "chunks_baseline_fixed.jsonl"
RAG_CHUNKS_SECTION_PATH = RAG_CHUNKS_DIR / "chunks_section_aware.jsonl"
RAG_CHUNKING_REPORT_PATH = RAG_REPORTS_DIR / "chunking_report.json"
RAG_CHUNKING_EXAMPLES_PATH = RAG_REPORTS_DIR / "chunking_examples.csv"

# ---------------------------------------------------------------------------
# Source types
# ---------------------------------------------------------------------------
SOURCE_TYPE_DOCS = "docs"
SOURCE_TYPE_ISSUE = "issue"
SOURCE_TYPE_COMMENT = "comment"

# ---------------------------------------------------------------------------
# Chunking strategy names
# ---------------------------------------------------------------------------
STRATEGY_BASELINE_FIXED = "baseline_fixed"
STRATEGY_SECTION_AWARE = "section_aware"

# ---------------------------------------------------------------------------
# Candidate embedding models (final choice TBD — selected in RAG-4)
# ---------------------------------------------------------------------------
CANDIDATE_EMBEDDING_MODELS = (
    "sentence-transformers/all-MiniLM-L6-v2",  # fast, strong general baseline
    "sentence-transformers/all-mpnet-base-v2",  # higher quality, slower
    "BAAI/bge-small-en-v1.5",  # strong retrieval, compact
    "BAAI/bge-base-en-v1.5",  # best BEIR benchmark scores
)

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
BASELINE_FIXED_CHUNK_CHARS = 512
SECTION_AWARE_MAX_CHARS = 1024
CHUNK_OVERLAP_CHARS = 64
MIN_CHUNK_CHARS = 40

# Tokens that justify keeping a chunk even if it is shorter than MIN_CHUNK_CHARS.
# Matched case-insensitively as substrings of the cleaned chunk text.
TINY_CHUNK_HIGH_SIGNAL_TOKENS: frozenset[str] = frozenset(
    {
        "kubectl",
        "kubelet",
        "apiversion",
        "kind:",
        "error",
        "exception",
        "failed",
        "service",
        "pod",
        "deployment",
        "endpointslice",
        "dns",
        "dra",
        "resourceclaim",
    }
)

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
DEFAULT_TOP_K = 5
DEFAULT_RERANK_TOP_K = 3
HYBRID_ALPHA_CANDIDATES = (0.3, 0.5, 0.7)  # alpha = weight of dense vs sparse

# ---------------------------------------------------------------------------
# Eval metric names
# ---------------------------------------------------------------------------
METRIC_HIT_AT_5 = "hit_at_5"
METRIC_MRR_AT_10 = "mrr_at_10"
METRIC_RECALL_AT_5 = "recall_at_5"
METRIC_FAITHFULNESS = "faithfulness"
METRIC_ANSWER_RELEVANCY = "answer_relevancy"

__all__ = [
    "RAG_DATA_DIR",
    "RAG_RAW_DOCS_DIR",
    "RAG_PROCESSED_DIR",
    "RAG_CHUNKS_DIR",
    "RAG_REPORTS_DIR",
    "RAG_FIGURES_DIR",
    "RAG_GOLDEN_DIR",
    "RAG_GOLDEN_CANDIDATES_PATH",
    "RAG_GOLDEN_CANDIDATES_SUMMARY_PATH",
    "RAG_GOLDEN_REVIEW_CSV_PATH",
    "RAG_GOLDEN_REVIEW_SUMMARY_PATH",
    "RAG_GOLDEN_PATH",
    "RAG_GOLDEN_SUMMARY_PATH",
    "RAG_HELDOUT_CANDIDATES_PATH",
    "RAG_ISSUES_WITH_COMMENTS_PATH",
    "RAG_DOC_SOURCES_PATH",
    "RAG_CORPUS_MANIFEST_PATH",
    "RAG_LEAKAGE_REPORT_PATH",
    "RAG_CORPUS_COLLECTION_REPORT_PATH",
    "RAG_CHUNKS_BASELINE_PATH",
    "RAG_CHUNKS_SECTION_PATH",
    "RAG_CHUNKING_REPORT_PATH",
    "RAG_CHUNKING_EXAMPLES_PATH",
    "SOURCE_TYPE_DOCS",
    "SOURCE_TYPE_ISSUE",
    "SOURCE_TYPE_COMMENT",
    "STRATEGY_BASELINE_FIXED",
    "STRATEGY_SECTION_AWARE",
    "CANDIDATE_EMBEDDING_MODELS",
    "BASELINE_FIXED_CHUNK_CHARS",
    "SECTION_AWARE_MAX_CHARS",
    "CHUNK_OVERLAP_CHARS",
    "MIN_CHUNK_CHARS",
    "TINY_CHUNK_HIGH_SIGNAL_TOKENS",
    "DEFAULT_TOP_K",
    "DEFAULT_RERANK_TOP_K",
    "HYBRID_ALPHA_CANDIDATES",
    "METRIC_HIT_AT_5",
    "METRIC_MRR_AT_10",
    "METRIC_RECALL_AT_5",
    "METRIC_FAITHFULNESS",
    "METRIC_ANSWER_RELEVANCY",
]
