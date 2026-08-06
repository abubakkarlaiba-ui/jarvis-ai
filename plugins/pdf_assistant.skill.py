"""
Skill: PDF Assistant
====================
Extracts text and metadata from PDF files, searches within documents,
and supports batch processing of multiple PDFs.

Falls back gracefully if PyPDF2 or pymupdf is not installed.
"""

from __future__ import annotations

import os
from pathlib import Path

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

_PDF_LIB = None
try:
    import pymupdf as _fitz
    _PDF_LIB = "pymupdf"
except ImportError:
    try:
        import PyPDF2 as _pypdf2
        _PDF_LIB = "pypdf2"
    except ImportError:
        _PDF_LIB = None


def _read_text_pypdf2(path: str, pages: list[int] | None = None) -> dict:
    from PyPDF2 import PdfReader
    reader = PdfReader(path)
    meta = reader.metadata or {}
    total = len(reader.pages)
    target = pages if pages else list(range(total))
    text_parts = {}
    for p in target:
        if 0 <= p < total:
            text_parts[p] = reader.pages[p].extract_text() or ""
    return {
        "text": text_parts,
        "total_pages": total,
        "metadata": {
            "title": getattr(meta, "title", None),
            "author": getattr(meta, "author", None),
            "subject": getattr(meta, "subject", None),
        },
    }


def _read_text_pymupdf(path: str, pages: list[int] | None = None) -> dict:
    doc = _fitz.open(path)
    total = doc.page_count
    meta = doc.metadata or {}
    target = pages if pages else list(range(total))
    text_parts = {}
    for p in target:
        if 0 <= p < total:
            text_parts[p] = doc[p].get_text()
    doc.close()
    return {
        "text": text_parts,
        "total_pages": total,
        "metadata": {
            "title": meta.get("title"),
            "author": meta.get("author"),
            "subject": meta.get("subject"),
        },
    }


def _read_pdf(path: str, pages: list[int] | None = None) -> dict:
    if _PDF_LIB == "pymupdf":
        return _read_text_pymupdf(path, pages)
    elif _PDF_LIB == "pypdf2":
        return _read_text_pypdf2(path, pages)
    raise RuntimeError("No PDF library available. Install pymupdf or PyPDF2.")


def _search_text(text: str, query: str) -> list[str]:
    results = []
    lower_text = text.lower()
    lower_query = query.lower()
    idx = 0
    while True:
        pos = lower_text.find(lower_query, idx)
        if pos == -1:
            break
        start = max(0, pos - 60)
        end = min(len(text), pos + len(query) + 60)
        snippet = text[start:end].replace("\n", " ").strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        results.append(snippet)
        idx = pos + 1
    return results


class PDFAssistantSkill(BaseSkill):
    """Reads, searches, and extracts content from PDF files.

    Example:
        User: "Read the first page of report.pdf"
        JARVIS: "Page 1 content: ..."

        User: "Search for 'revenue' in report.pdf"
        JARVIS: "Found 3 occurrences: ..."
    """

    metadata = SkillMetadata(
        name="pdf_assistant",
        version="1.0.0",
        description="PDF text extraction, metadata, and search",
        author="JARVIS Team",
        tags=["pdf", "document", "text", "extraction"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        if _PDF_LIB is None:
            return SkillResult(
                success=False,
                error="No PDF library installed. Install pymupdf or PyPDF2.",
            )

        action = context.parameters.get("action", "read")
        file_path = context.parameters.get("file_path", "").strip()

        if not file_path:
            return SkillResult(success=False, error="No file_path provided.")

        path = Path(file_path)
        if not path.exists():
            return SkillResult(success=False, error=f"File not found: {file_path}")
        if not path.suffix.lower() == ".pdf":
            return SkillResult(success=False, error="File is not a PDF.")

        try:
            if action == "read":
                return await self._action_read(path, context)
            elif action == "search":
                return await self._action_search(path, context)
            elif action == "metadata":
                return await self._action_metadata(path)
            elif action == "batch":
                return await self._action_batch(context)
            else:
                return SkillResult(
                    success=False,
                    error=f"Unknown action: {action}. Use read, search, metadata, or batch.",
                )
        except Exception as exc:
            return SkillResult(success=False, error=f"PDF error: {exc}")

    async def _action_read(self, path: Path, context: SkillContext) -> SkillResult:
        raw_pages = context.parameters.get("pages")
        pages = None
        if raw_pages:
            if isinstance(raw_pages, list):
                pages = [int(p) - 1 for p in raw_pages]
            else:
                pages = [int(raw_pages) - 1]
        data = _read_pdf(str(path), pages)
        lines = [f"Pages: {data['total_pages']}"]
        meta = data["metadata"]
        if meta.get("title"):
            lines.append(f"Title: {meta['title']}")
        if meta.get("author"):
            lines.append(f"Author: {meta['author']}")
        lines.append("")
        for pg, txt in sorted(data["text"].items()):
            lines.append(f"--- Page {pg + 1} ---")
            lines.append(txt[:3000])
            lines.append("")
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"total_pages": data["total_pages"], "metadata": meta},
        )

    async def _action_search(self, path: Path, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", "").strip()
        if not query:
            return SkillResult(success=False, error="No search query provided.")
        data = _read_pdf(str(path))
        all_hits = []
        for pg, txt in sorted(data["text"].items()):
            snippets = _search_text(txt, query)
            for s in snippets:
                all_hits.append(f"Page {pg + 1}: {s}")
        if not all_hits:
            return SkillResult(
                success=True,
                output=f"No occurrences of '{query}' found in {path.name}.",
                metadata={"query": query, "hits": 0},
            )
        lines = [f"Found {len(all_hits)} occurrence(s) of '{query}':", ""]
        lines.extend(all_hits[:20])
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"query": query, "hits": len(all_hits)},
        )

    async def _action_metadata(self, path: Path) -> SkillResult:
        data = _read_pdf(str(path))
        meta = data["metadata"]
        lines = [
            f"File: {path.name}",
            f"Pages: {data['total_pages']}",
            f"Title: {meta.get('title') or 'N/A'}",
            f"Author: {meta.get('author') or 'N/A'}",
            f"Subject: {meta.get('subject') or 'N/A'}",
        ]
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"total_pages": data["total_pages"], "metadata": meta},
        )

    async def _action_batch(self, context: SkillContext) -> SkillResult:
        file_paths = context.parameters.get("file_paths", [])
        if not file_paths:
            return SkillResult(success=False, error="No file_paths provided.")
        results = []
        for fp in file_paths:
            p = Path(fp)
            if not p.exists():
                results.append(f"{fp}: NOT FOUND")
                continue
            try:
                data = _read_pdf(str(p))
                total = data["total_pages"]
                snippet = ""
                if data["text"]:
                    first_pg = min(data["text"].keys())
                    snippet = data["text"][first_pg][:100].replace("\n", " ")
                results.append(f"{p.name}: {total} pages | {snippet}...")
            except Exception as exc:
                results.append(f"{fp}: ERROR - {exc}")
        return SkillResult(
            success=True,
            output="\n".join(results),
            metadata={"files_processed": len(results)},
        )
