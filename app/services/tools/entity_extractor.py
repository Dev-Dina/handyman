"""Rule-based entity extraction for Kubernetes issue text."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

try:
    from app.infra.redaction import redact as _redact
except ImportError:
    _redact = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_RE_VERSION = re.compile(
    r"\b(?:Kubernetes\s+|k8s\s+|v)?v?(\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?)\b",
    re.IGNORECASE,
)

_RE_VERSION_STRICT = re.compile(
    r"""
    (?:
        v\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?   # v1.29.0 or v1.30
        |
        (?:Kubernetes|k8s)\s+\d+\.\d+(?:\.\d+)?    # Kubernetes 1.31
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RE_COMMAND = re.compile(
    r"\b(kubectl|kubeadm|kubelet)\b(?:\s+[a-z][-a-z0-9]*)*",
    re.IGNORECASE,
)

_COMPONENTS = frozenset(
    [
        "kubelet",
        "kube-apiserver",
        "kube-scheduler",
        "scheduler",
        "controller-manager",
        "kube-controller-manager",
        "etcd",
        "kube-proxy",
        "coredns",
        "kube-dns",
    ]
)

_RE_COMPONENT = re.compile(
    r"\b("
    + "|".join(re.escape(c) for c in sorted(_COMPONENTS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

_RE_ERROR = re.compile(
    r"\b([A-Z][a-zA-Z0-9]*(?:Error|Exception|Failure|BackOff|Backoff|Failed|Timeout|Panic|Crash|OOM|Killed|Evicted|Pending|Unknown))\b",
)

_RESOURCES = frozenset(
    [
        "Pod",
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "ReplicaSet",
        "Service",
        "Ingress",
        "ConfigMap",
        "Secret",
        "Job",
        "CronJob",
        "Namespace",
        "PersistentVolume",
        "PersistentVolumeClaim",
        "StorageClass",
        "ServiceAccount",
        "ClusterRole",
        "ClusterRoleBinding",
        "Role",
        "RoleBinding",
        "HorizontalPodAutoscaler",
        "NetworkPolicy",
        "ResourceQuota",
        "LimitRange",
        "Node",
    ]
)

_RE_RESOURCE = re.compile(
    r"\b("
    + "|".join(re.escape(r) for r in sorted(_RESOURCES, key=len, reverse=True))
    + r")\b",
)

_RE_PATH = re.compile(
    r"(?:^|(?<=\s)|(?<=[\"'`(]))(/(?:[^/\s\"'`)\]>]+/)*[^/\s\"'`)\]>]+)",
)

_RE_IMAGE = re.compile(
    r"""
    (?:
        [a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?  # registry host
        (?:\.[a-zA-Z]{2,})+                                # TLD(s) — makes it a registry
        (?::\d{1,5})?                                       # optional port
        /
    )?
    [a-z0-9](?:[a-z0-9._\-/]*[a-z0-9])?                   # image path
    (?::[a-zA-Z0-9._\-]+)?                                  # tag
    (?:@sha256:[a-f0-9]{64})?                               # digest
    """,
    re.VERBOSE,
)

_RE_IMAGE_STRICT = re.compile(
    r"""
    (?:
        (?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,})+(?::\d{1,5})?/)?
        [a-z0-9][a-z0-9._\-/]*
        (?::[a-zA-Z0-9._\-]+|@sha256:[a-f0-9]{64})
    )
    """,
    re.VERBOSE,
)

_RE_URL = re.compile(
    r"https?://[^\s\"'<>\])]+"
    r"|"
    r"(?:www\.)[^\s\"'<>\])]+",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract Kubernetes-related entities from issue title/body text.

    Returns a dict with keys: versions, commands, components, errors,
    resources, paths, images, urls.
    """
    if _redact is not None:
        text = _redact(text)

    return {
        "versions": _extract_versions(text),
        "commands": _extract_commands(text),
        "components": _extract_components(text),
        "errors": _extract_errors(text),
        "resources": _extract_resources(text),
        "paths": _extract_paths(text),
        "images": _extract_images(text),
        "urls": _extract_urls(text),
    }


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def _unique_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _extract_versions(text: str) -> list[str]:
    matches = _RE_VERSION_STRICT.findall(text)
    # Also capture bare vX.Y.Z patterns
    bare = re.findall(
        r"\bv\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?\b", text, re.IGNORECASE
    )
    combined = matches + bare
    return _unique_ordered(combined)


def _extract_commands(text: str) -> list[str]:
    raw: list[str] = []
    for m in _RE_COMMAND.finditer(text):
        raw.append(m.group(0).strip())
    return _unique_ordered(raw)


def _extract_components(text: str) -> list[str]:
    raw: list[str] = []
    for m in _RE_COMPONENT.finditer(text):
        raw.append(m.group(0).lower())
    return _unique_ordered(raw)


def _extract_errors(text: str) -> list[str]:
    raw: list[str] = []
    for m in _RE_ERROR.finditer(text):
        raw.append(m.group(0))
    return _unique_ordered(raw)


def _extract_resources(text: str) -> list[str]:
    raw: list[str] = []
    for m in _RE_RESOURCE.finditer(text):
        raw.append(m.group(0))
    return _unique_ordered(raw)


def _extract_paths(text: str) -> list[str]:
    # Strip URLs first to avoid overlapping
    cleaned = _RE_URL.sub(" ", text)
    raw: list[str] = []
    for m in _RE_PATH.finditer(cleaned):
        path = m.group(1)
        # Filter noise: must have at least one slash and a non-trivial segment
        if len(path) > 1 and "/" in path:
            raw.append(path)
    return _unique_ordered(raw)


def _extract_images(text: str) -> list[str]:
    # Remove URLs first
    cleaned = _RE_URL.sub(" ", text)
    raw: list[str] = []
    for m in _RE_IMAGE_STRICT.finditer(cleaned):
        candidate = m.group(0).strip()
        if candidate:
            raw.append(candidate)
    return _unique_ordered(raw)


def _extract_urls(text: str) -> list[str]:
    raw: list[str] = []
    for m in _RE_URL.finditer(text):
        raw.append(m.group(0).rstrip(".,;:"))
    return _unique_ordered(raw)
