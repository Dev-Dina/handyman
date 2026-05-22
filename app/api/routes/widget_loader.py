"""Serves GET /widget.js — the host-page loader script.

No auth, no DB, no business logic. Returns a small JavaScript snippet
that the host page includes via a <script> tag. The script reads
data-widget-id, creates an iframe, and wires postMessage resize.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.services.widgets.loader import build_loader_script

router = APIRouter(tags=["widget-loader"])


@router.get("/widget.js", include_in_schema=False)
async def serve_widget_loader() -> Response:
    return Response(
        content=build_loader_script(),
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
