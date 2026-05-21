"""Tests for rule-based Kubernetes entity extractor."""

from __future__ import annotations

import pytest

from app.services.tools.entity_extractor import extract_entities

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ISSUE_FULL = """
Title: CrashLoopBackOff on kubelet after upgrade to v1.29.3

We upgraded our cluster from Kubernetes 1.28.5 to v1.29.3 and now one of the
nodes is in a CrashLoopBackOff state. The kubelet and kube-apiserver logs both
show UnexpectedAdmissionError.

Reproduction:
  kubectl get pods -n kube-system
  kubectl describe pod coredns-abc123 -n kube-system
  kubeadm upgrade apply v1.29.3

Relevant config at /etc/kubernetes/manifests/kube-apiserver.yaml and
/var/lib/kubelet/config.yaml.

We are running image registry.k8s.io/kube-apiserver:v1.29.3 and
ghcr.io/my-org/custom-init:1.2.3@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

The etcd and kube-proxy also seem affected.

Pod and Deployment resources behave normally, but StatefulSet rollouts fail.

See also: https://github.com/kubernetes/kubernetes/issues/99999
"""

ISSUE_VERSION_ONLY = "Running Kubernetes 1.31 and v1.30.0-beta.1 in staging."

ISSUE_ERRORS = (
    "Node shows OOMKilled then Evicted. "
    "Container went into ImagePullBackOff followed by CrashLoopBackOff. "
    "kube-scheduler logged a Timeout."
)

ISSUE_PATHS = (
    "Config at /etc/kubernetes/pki/ca.crt and /var/lib/kubelet/config.yaml. "
    "Check /tmp/debug.log for details."
)

ISSUE_URLS = (
    "See https://kubernetes.io/docs/concepts/ and "
    "https://github.com/kubernetes/kubernetes/issues/12345 for context."
)

ISSUE_IMAGES = (
    "Image: registry.k8s.io/pause:3.9 and docker.io/library/nginx:1.25-alpine are used."
)

ISSUE_COMPONENTS = (
    "The kube-controller-manager, kube-scheduler, and etcd pods are healthy. "
    "kube-proxy on worker nodes shows errors."
)

ISSUE_COMMANDS = (
    "Run kubectl apply -f deployment.yaml then "
    "kubectl rollout status deployment/myapp. "
    "Also kubeadm init and kubelet restart needed."
)

ISSUE_RESOURCES = (
    "Apply the ConfigMap and Secret before the Deployment. "
    "The Ingress points to the Service. "
    "CronJob triggers a Job every hour."
)


# ---------------------------------------------------------------------------
# Version extraction
# ---------------------------------------------------------------------------


def test_version_vprefix():
    result = extract_entities("Upgrading from v1.28.0 to v1.29.3.")
    assert "v1.28.0" in result["versions"]
    assert "v1.29.3" in result["versions"]


def test_version_kubernetes_prefix():
    result = extract_entities(ISSUE_VERSION_ONLY)
    versions = result["versions"]
    assert any("1.31" in v for v in versions)
    assert any("1.30.0" in v or "1.30" in v for v in versions)


def test_version_full_issue():
    result = extract_entities(ISSUE_FULL)
    versions = result["versions"]
    assert any("1.29.3" in v for v in versions)
    assert any("1.28.5" in v or "1.28" in v for v in versions)


def test_version_prerelease():
    result = extract_entities("Testing v1.30.0-beta.1 and v1.31.0-rc.2.")
    versions = result["versions"]
    assert any("1.30.0-beta.1" in v or "1.30" in v for v in versions)


def test_version_no_duplicates():
    result = extract_entities("Use v1.29.0 and v1.29.0 again.")
    assert (
        result["versions"].count(result["versions"][0]) == 1
        if result["versions"]
        else True
    )


# ---------------------------------------------------------------------------
# Command extraction
# ---------------------------------------------------------------------------


def test_commands_basic():
    result = extract_entities(ISSUE_COMMANDS)
    cmds = " ".join(result["commands"])
    assert "kubectl" in cmds
    assert "kubeadm" in cmds
    assert "kubelet" in cmds


def test_commands_full_issue():
    result = extract_entities(ISSUE_FULL)
    cmds = " ".join(result["commands"])
    assert "kubectl" in cmds
    assert "kubeadm" in cmds


# ---------------------------------------------------------------------------
# Component extraction
# ---------------------------------------------------------------------------


def test_components_basic():
    result = extract_entities(ISSUE_COMPONENTS)
    comps = result["components"]
    assert any("etcd" in c for c in comps)
    assert any("kube-proxy" in c for c in comps)
    assert any("scheduler" in c or "kube-scheduler" in c for c in comps)


def test_components_full_issue():
    result = extract_entities(ISSUE_FULL)
    comps = result["components"]
    assert any("kubelet" in c for c in comps)
    assert any("etcd" in c for c in comps)
    assert any("kube-proxy" in c for c in comps)
    assert any("kube-apiserver" in c for c in comps)


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------


def test_errors_basic():
    result = extract_entities(ISSUE_ERRORS)
    errors = result["errors"]
    assert "CrashLoopBackOff" in errors or any("CrashLoop" in e for e in errors)
    assert "ImagePullBackOff" in errors or any("ImagePull" in e for e in errors)
    assert any("OOM" in e or "Evicted" in e for e in errors)


def test_errors_full_issue():
    result = extract_entities(ISSUE_FULL)
    errors = result["errors"]
    assert any("CrashLoopBackOff" in e for e in errors)
    assert any("UnexpectedAdmissionError" in e for e in errors)


# ---------------------------------------------------------------------------
# Resource extraction
# ---------------------------------------------------------------------------


def test_resources_basic():
    result = extract_entities(ISSUE_RESOURCES)
    res = result["resources"]
    assert "ConfigMap" in res
    assert "Secret" in res
    assert "Deployment" in res
    assert "Ingress" in res
    assert "Service" in res
    assert "CronJob" in res
    assert "Job" in res


def test_resources_full_issue():
    result = extract_entities(ISSUE_FULL)
    res = result["resources"]
    assert "Pod" in res
    assert "Deployment" in res
    assert "StatefulSet" in res


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------


def test_paths_basic():
    result = extract_entities(ISSUE_PATHS)
    paths = result["paths"]
    assert any("/etc/kubernetes/pki/ca.crt" in p for p in paths)
    assert any("/var/lib/kubelet/config.yaml" in p for p in paths)


def test_paths_full_issue():
    result = extract_entities(ISSUE_FULL)
    paths = result["paths"]
    assert any("/etc/kubernetes" in p for p in paths)
    assert any("/var/lib/kubelet" in p for p in paths)


def test_paths_no_urls_leaked():
    text = "See https://kubernetes.io/docs/setup/ and /etc/hosts."
    result = extract_entities(text)
    for p in result["paths"]:
        assert not p.startswith("http")


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------


def test_images_basic():
    result = extract_entities(ISSUE_IMAGES)
    images = result["images"]
    assert any("pause" in img and "3.9" in img for img in images)
    assert any("nginx" in img for img in images)


def test_images_with_digest():
    text = "Using ghcr.io/my-org/app:latest@sha256:" + "a" * 64
    result = extract_entities(text)
    assert any("sha256" in img for img in result["images"])


def test_images_full_issue():
    result = extract_entities(ISSUE_FULL)
    images = result["images"]
    assert any("kube-apiserver" in img for img in images)


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------


def test_urls_basic():
    result = extract_entities(ISSUE_URLS)
    urls = result["urls"]
    assert any("kubernetes.io" in u for u in urls)
    assert any("github.com" in u for u in urls)


def test_urls_full_issue():
    result = extract_entities(ISSUE_FULL)
    urls = result["urls"]
    assert any("github.com" in u for u in urls)


def test_urls_no_trailing_punctuation():
    result = extract_entities("Check https://example.com/path.")
    urls = result["urls"]
    assert all(not u.endswith(".") for u in urls)


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


def test_return_keys():
    result = extract_entities("some text")
    expected = {
        "versions",
        "commands",
        "components",
        "errors",
        "resources",
        "paths",
        "images",
        "urls",
    }
    assert set(result.keys()) == expected


def test_all_values_are_lists():
    result = extract_entities("some text")
    for key, val in result.items():
        assert isinstance(val, list), f"{key} is not a list"


def test_empty_input():
    result = extract_entities("")
    for val in result.values():
        assert val == []


def test_no_false_positives_on_unrelated_text():
    result = extract_entities("The quick brown fox jumps over the lazy dog.")
    assert result["versions"] == []
    assert result["commands"] == []
    assert result["images"] == []
    assert result["urls"] == []
