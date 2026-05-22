"""Reusable UI components for the AI Ops Control Center."""

from __future__ import annotations


def status_badge(ok: bool | None) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚠️"
