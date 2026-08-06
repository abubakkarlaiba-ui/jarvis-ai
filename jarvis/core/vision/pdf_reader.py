"""
PDF reader for JARVIS vision system.
======================================
Read and extract content from PDF documents.

Supports:
    - Text extraction
    - Page rendering to images
    - OCR on scanned PDFs
    - PDF metadata extraction
    - Page-by-page processing

Usage:
    reader = PDFReader(config)
    result = await reader.extract_text("document.pdf")
    result = await reader.render_page("document.pdf", page=1)
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask

logger = logging.getLogger(__name__)


class PDFReader:
    """Read and extract content from PDF files.

    Example:
        config = VisionConfig(pdf_enabled=True)
        reader = PDFReader(config)
        result = await reader.extract_text("report.pdf")
        result = await reader.render_page("report.pdf", page=1)
    """

    def __init__(self, config: VisionConfig):
        self._config = config

    async def extract_text(self, file_path: str, max_pages: int | None = None) -> VisionResult:
        """Extract text from a PDF file.

        Args:
            file_path: Path to PDF file.
            max_pages: Maximum pages to process.

        Returns:
            VisionResult with extracted text.
        """
        start = time.perf_counter()
        path = Path(file_path)
        if not path.exists():
            return VisionResult(success=False, message=f"File not found: {file_path}")

        max_pg = max_pages or self._config.pdf_max_pages

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            pages = []
            full_text = []

            for i, page in enumerate(doc):
                if i >= max_pg:
                    break
                text = page.get_text()
                pages.append({
                    "page": i + 1,
                    "text": text,
                    "char_count": len(text),
                })
                full_text.append(text)

            doc.close()

            combined = "\n\n".join(full_text)
            elapsed = (time.perf_counter() - start) * 1000

            return VisionResult(
                success=True,
                message=f"Extracted {len(combined)} chars from {len(pages)} pages",
                task=VisionTask.PDF_READ,
                data={
                    "text": combined,
                    "pages": pages,
                    "total_pages": len(pages),
                    "total_chars": len(combined),
                },
                duration_ms=elapsed,
            )

        except ImportError:
            return VisionResult(
                success=False,
                message="PyMuPDF not installed: pip install PyMuPDF",
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"PDF extraction failed: {exc}", duration_ms=elapsed)

    async def render_page(self, file_path: str, page: int = 1, dpi: int = 150) -> VisionResult:
        """Render a PDF page as an image.

        Args:
            file_path: Path to PDF file.
            page: Page number (1-indexed).
            dpi: Rendering DPI.

        Returns:
            VisionResult with rendered page as numpy array.
        """
        start = time.perf_counter()
        path = Path(file_path)
        if not path.exists():
            return VisionResult(success=False, message=f"File not found: {file_path}")

        try:
            import fitz
            doc = fitz.open(str(path))
            if page < 1 or page > len(doc):
                doc.close()
                return VisionResult(success=False, message=f"Page {page} out of range (1-{len(doc)})")

            pg = doc[page - 1]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = pg.get_pixmap(matrix=mat)

            import cv2
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            elif pix.n == 1:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)

            doc.close()
            elapsed = (time.perf_counter() - start) * 1000

            return VisionResult(
                success=True,
                message=f"Rendered page {page}: {pix.width}x{pix.height}",
                task=VisionTask.PDF_READ,
                data={"frame": img_array, "width": pix.width, "height": pix.height, "page": page},
                duration_ms=elapsed,
            )

        except ImportError:
            return VisionResult(success=False, message="PyMuPDF not installed: pip install PyMuPDF")
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Render failed: {exc}", duration_ms=elapsed)

    async def get_metadata(self, file_path: str) -> VisionResult:
        """Get PDF metadata."""
        path = Path(file_path)
        if not path.exists():
            return VisionResult(success=False, message=f"File not found: {file_path}")

        try:
            import fitz
            doc = fitz.open(str(path))
            meta = doc.metadata
            pages = len(doc)
            doc.close()

            return VisionResult(
                success=True,
                message=f"PDF metadata: {pages} pages",
                data={
                    "title": meta.get("title", ""),
                    "author": meta.get("author", ""),
                    "subject": meta.get("subject", ""),
                    "creator": meta.get("creator", ""),
                    "producer": meta.get("producer", ""),
                    "pages": pages,
                    "file_size": path.stat().st_size,
                },
            )
        except ImportError:
            return VisionResult(success=False, message="PyMuPDF not installed")
        except Exception as exc:
            return VisionResult(success=False, message=f"Metadata failed: {exc}")

    async def render_all_pages(self, file_path: str, dpi: int = 100, max_pages: int | None = None) -> VisionResult:
        """Render all pages as images.

        Args:
            file_path: Path to PDF file.
            dpi: Rendering DPI.
            max_pages: Maximum pages to render.

        Returns:
            VisionResult with list of rendered pages.
        """
        start = time.perf_counter()
        path = Path(file_path)
        if not path.exists():
            return VisionResult(success=False, message=f"File not found: {file_path}")

        try:
            import fitz
            doc = fitz.open(str(path))
            max_pg = max_pages or self._config.pdf_max_pages
            pages = []

            for i in range(min(len(doc), max_pg)):
                pg = doc[i]
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = pg.get_pixmap(matrix=mat)

                import cv2
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

                pages.append({"page": i + 1, "frame": img, "width": pix.width, "height": pix.height})

            doc.close()
            elapsed = (time.perf_counter() - start) * 1000

            return VisionResult(
                success=True,
                message=f"Rendered {len(pages)} pages",
                data={"pages": pages},
                duration_ms=elapsed,
            )

        except ImportError:
            return VisionResult(success=False, message="PyMuPDF not installed")
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Render all failed: {exc}", duration_ms=elapsed)
