"""
UI routes — serve static files and the main SPA.
================================================
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])

UI_DIR = Path(__file__).parent
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"


@router.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main JARVIS UI."""
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>JARVIS UI</h1><p>UI files not found.</p>", status_code=200)


@router.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    """Serve static files (CSS, JS, images)."""
    full_path = STATIC_DIR / file_path
    if full_path.exists() and full_path.is_file():
        # Determine content type
        suffix = full_path.suffix.lower()
        content_types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }
        content_type = content_types.get(suffix, "application/octet-stream")
        return FileResponse(
            path=str(full_path),
            media_type=content_type,
            headers={"Cache-Control": "no-cache"},
        )
    return HTMLResponse(content="Not found", status_code=404)


@router.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/x-icon")
    return HTMLResponse(content="", status_code=204)
