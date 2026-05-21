"""Deterministic query transforms for Kubernetes RAG retrieval.

Shared by pipelines/rag/eval_retrieval.py (offline eval) and the runtime
retrieval service. No external dependencies; safe to import anywhere.
"""

from __future__ import annotations

import re

# Kubernetes/cloud-native vocabulary that boosts retrieval signal
_K8S_TERMS: frozenset[str] = frozenset(
    {
        "pod",
        "pods",
        "node",
        "nodes",
        "namespace",
        "namespaces",
        "service",
        "services",
        "deployment",
        "deployments",
        "container",
        "containers",
        "kubectl",
        "kubelet",
        "kubeadm",
        "apiserver",
        "etcd",
        "scheduler",
        "controller",
        "ingress",
        "configmap",
        "secret",
        "pvc",
        "pv",
        "replicaset",
        "statefulset",
        "daemonset",
        "cronjob",
        "job",
        "serviceaccount",
        "rbac",
        "clusterrole",
        "rolebinding",
        "crd",
        "endpoint",
        "endpointslice",
        "resourcequota",
        "networkpolicy",
        "hpa",
        "vpa",
        "storageclass",
        "webhook",
        "admission",
        "mutating",
        "validating",
        "finalizer",
        "taint",
        "toleration",
        "affinity",
        "priorityclass",
        "resourceclaim",
        "dra",
        "csi",
        "cni",
        "cri",
    }
)

_CAMEL_RE = re.compile(r"\b[a-z]+[A-Z][a-zA-Z0-9]*\b")
_UPPER_DIGIT_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,}\b")

VALID_TRANSFORMS = ("none", "technical_terms")


def apply(question: str, mode: str) -> str:
    """Apply a named transform to a query string.

    Args:
        question: raw question text
        mode: one of VALID_TRANSFORMS

    Returns:
        transformed question string (mode="none" returns question unchanged)
    """
    if mode == "technical_terms":
        return _expand_technical(question)
    return question


def _expand_technical(q: str) -> str:
    """Append extracted Kubernetes/code-shaped tokens to boost retrieval signal."""
    tokens: set[str] = set()
    for word in re.findall(r"\b\w[\w/.\-]*\b", q):
        if word.lower() in _K8S_TERMS:
            tokens.add(word.lower())
    tokens.update(_CAMEL_RE.findall(q))
    tokens.update(_UPPER_DIGIT_RE.findall(q))
    if not tokens:
        return q
    return q + " " + " ".join(sorted(tokens))
