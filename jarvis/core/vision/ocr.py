"""
OCR engine for JARVIS vision system.
======================================
Extract text from images using multiple OCR backends.

Supports:
    - EasyOCR (default, GPU-accelerated)
    - Tesseract
    - PaddleOCR
    - Multi-language support
    - Text region detection

Usage:
    ocr = OCREngine(config)
    await ocr.initialize()
    result = await ocr.extract_text(image)
    result = await ocr.extract_from_file("screenshot.png")
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask, OCRResult

logger = logging.getLogger(__name__)


class OCREngine:
    """Extract text from images using various OCR engines.

    Example:
        config = VisionConfig(ocr_engine="easyocr", ocr_languages=["en"])
        ocr = OCREngine(config)
        await ocr.initialize()
        result = await ocr.extract_text(frame)
        for item in result.data:
            print(item["text"])
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._reader: Any = None
        self._initialized = False

    async def initialize(self) -> VisionResult:
        """Initialize the OCR engine."""
        if not self._config.ocr_enabled:
            return VisionResult(success=False, message="OCR disabled in config")

        try:
            engine = self._config.ocr_engine.lower()

            if engine == "easyocr":
                import easyocr
                self._reader = easyocr.Reader(
                    self._config.ocr_languages,
                    gpu=False,
                    verbose=False,
                )
            elif engine == "tesseract":
                import pytesseract
                self._reader = pytesseract
            elif engine == "paddleocr":
                from paddleocr import PaddleOCR
                self._reader = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            else:
                return VisionResult(success=False, message=f"Unknown OCR engine: {engine}")

            self._initialized = True
            return VisionResult(
                success=True,
                message=f"OCR engine initialized: {engine}",
                task=VisionTask.OCR,
            )

        except ImportError as exc:
            return VisionResult(
                success=False,
                message=f"OCR library not installed: {exc}. Install with: pip install {self._config.ocr_engine}",
            )
        except Exception as exc:
            return VisionResult(success=False, message=f"OCR init failed: {exc}", error=str(exc))

    async def extract_text(
        self,
        image: np.ndarray | str,
        language: str | None = None,
    ) -> VisionResult:
        """Extract text from an image.

        Args:
            image: numpy array or file path.
            language: Optional language override.

        Returns:
            VisionResult with list of OCRResult dicts.
        """
        start = time.perf_counter()
        if not self._initialized:
            return VisionResult(success=False, message="OCR not initialized")

        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read image: {image}")
            else:
                img = image

            engine = self._config.ocr_engine.lower()
            results = []

            if engine == "easyocr":
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                raw = self._reader.readtext(rgb)
                for (bbox, text, conf) in raw:
                    x1, y1 = int(bbox[0][0]), int(bbox[0][1])
                    x2, y2 = int(bbox[2][0]), int(bbox[2][1])
                    results.append(OCRResult(
                        text=text,
                        confidence=float(conf),
                        bbox=(x1, y1, x2, y2),
                    ))

            elif engine == "tesseract":
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                data = self._reader.image_to_data(rgb, output_type=self._reader.Output.DICT)
                for i in range(len(data["text"])):
                    text = data["text"][i].strip()
                    conf = int(data["conf"][i])
                    if text and conf > 0:
                        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                        results.append(OCRResult(
                            text=text,
                            confidence=conf / 100.0,
                            bbox=(x, y, x + w, y + h),
                        ))

            elif engine == "paddleocr":
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                raw = self._reader.ocr(rgb, cls=True)
                if raw and raw[0]:
                    for line in raw[0]:
                        bbox_points = line[0]
                        text = line[1][0]
                        conf = line[1][1]
                        x1 = int(min(p[0] for p in bbox_points))
                        y1 = int(min(p[1] for p in bbox_points))
                        x2 = int(max(p[0] for p in bbox_points))
                        y2 = int(max(p[1] for p in bbox_points))
                        results.append(OCRResult(
                            text=text,
                            confidence=float(conf),
                            bbox=(x1, y1, x2, y2),
                        ))

            elapsed = (time.perf_counter() - start) * 1000
            full_text = " ".join(r.text for r in results)

            return VisionResult(
                success=True,
                message=f"Extracted {len(results)} text regions ({len(full_text)} chars)",
                task=VisionTask.OCR,
                data=[r.to_dict() for r in results],
                confidence=sum(r.confidence for r in results) / max(len(results), 1),
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("OCR failed: %s", exc)
            return VisionResult(success=False, message=f"OCR failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def extract_from_file(self, file_path: str) -> VisionResult:
        """Extract text from an image file."""
        return await self.extract_text(file_path)

    async def extract_full_text(self, image: np.ndarray | str) -> VisionResult:
        """Extract all text as a single string."""
        result = await self.extract_text(image)
        if result.success and result.data:
            full_text = " ".join(item["text"] for item in result.data)
            result.data = {"text": full_text, "regions": len(result.data)}
            result.message = f"Extracted {len(full_text)} characters"
        return result

    async def find_text(self, image: np.ndarray | str, query: str) -> VisionResult:
        """Find specific text in an image.

        Args:
            image: Image to search.
            query: Text to find.

        Returns:
            VisionResult with matching text locations.
        """
        result = await self.extract_text(image)
        if not result.success:
            return result

        query_lower = query.lower()
        matches = [
            item for item in result.data
            if query_lower in item["text"].lower()
        ]

        return VisionResult(
            success=True,
            message=f"Found {len(matches)} matches for '{query}'",
            task=VisionTask.OCR,
            data={"query": query, "matches": matches},
            confidence=max((m["confidence"] for m in matches), default=0),
        )
