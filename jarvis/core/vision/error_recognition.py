"""
Error message recognition for JARVIS vision system.
====================================================
Detect error messages, warnings, and异常 states in screenshots.

Supports:
    - Error dialog detection
    - Warning indicator detection
    - Error text recognition
    - Error pattern matching
    - Error severity classification

Usage:
    error_rec = ErrorRecognizer(config)
    result = await error_rec.detect(screenshot)
    result = await error_rec.find_error_text(screenshot)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask

logger = logging.getLogger(__name__)

ERROR_PATTERNS = [
    r"error",
    r"failed",
    r"failure",
    r"exception",
    r"cannot",
    r"unable",
    r"denied",
    r"refused",
    r"invalid",
    r"not found",
    r"missing",
    r"broken",
    r"fatal",
    r"critical",
    r"abort",
    r"crash",
    r"timeout",
    r"overload",
    r"overflow",
    r"null pointer",
    r"access violation",
    r"permission denied",
    r"out of memory",
    r"disk full",
    r"no space",
    r"connection refused",
    r"network unreachable",
    r"host unreachable",
    r"no route",
    r"ssl error",
    r"certificate",
    r"unauthorized",
    r"forbidden",
    r"not authorized",
]

WARNING_PATTERNS = [
    r"warning",
    r"warn",
    r"caution",
    r"attention",
    r"notice",
    r"alert",
    r"小心",
    r"注意",
]


class ErrorRecognizer:
    """Detect error messages and异常 states in screenshots.

    Example:
        config = VisionConfig(error_recognition_enabled=True)
        recognizer = ErrorRecognizer(config)
        result = await recognizer.detect(screenshot)
        if result.data["errors_found"]:
            print(result.data["errors"])
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._error_regex = re.compile("|".join(ERROR_PATTERNS), re.IGNORECASE)
        self._warning_regex = re.compile("|".join(WARNING_PATTERNS), re.IGNORECASE)

    async def detect(self, image: np.ndarray | str) -> VisionResult:
        """Detect errors in a screenshot.

        Args:
            image: Screenshot as numpy array or file path.

        Returns:
            VisionResult with detected errors.
        """
        start = time.perf_counter()
        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read: {image}")
            else:
                img = image

            errors = []
            warnings = []

            red_regions = self._detect_red_regions(img)
            for region in red_regions:
                errors.append({
                    "type": "visual",
                    "severity": "error",
                    "region": region,
                    "description": "Red indicator detected",
                })

            dialog = self._detect_dialog(img)
            if dialog:
                errors.append({
                    "type": "dialog",
                    "severity": "error",
                    "region": dialog,
                    "description": "Error dialog detected",
                })

            orange_regions = self._detect_color_regions(img, "orange")
            yellow_regions = self._detect_color_regions(img, "yellow")
            for region in orange_regions + yellow_regions:
                warnings.append({
                    "type": "visual",
                    "severity": "warning",
                    "region": region,
                    "description": "Warning indicator detected",
                })

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Found {len(errors)} error(s), {len(warnings)} warning(s)",
                task=VisionTask.ERROR_DETECT,
                data={
                    "errors_found": len(errors) > 0,
                    "errors": errors,
                    "warnings": warnings,
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                },
                confidence=0.7 if errors else 0.9,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Error detection failed: {exc}", duration_ms=elapsed)

    async def find_error_text(self, image: np.ndarray | str, ocr_engine: Any = None) -> VisionResult:
        """Find error text in an image using OCR.

        Args:
            image: Image to analyze.
            ocr_engine: Optional OCR engine instance.

        Returns:
            VisionResult with error text matches.
        """
        start = time.perf_counter()
        try:
            if isinstance(image, str):
                img = cv2.imread(image)
            else:
                img = image

            if ocr_engine:
                ocr_result = await ocr_engine.extract_text(img)
                if ocr_result.success:
                    texts = [item["text"] for item in ocr_result.data]
                else:
                    texts = []
            else:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                texts = [t.strip() for t in cv2.connectedComponentsWithStats(binary)[1].astype(str) if t.strip()]

            errors_found = []
            warnings_found = []

            for text in texts:
                if self._error_regex.search(text):
                    errors_found.append({"text": text, "type": "error_text"})
                elif self._warning_regex.search(text):
                    warnings_found.append({"text": text, "type": "warning_text"})

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Found {len(errors_found)} error texts, {len(warnings_found)} warning texts",
                data={
                    "errors": errors_found,
                    "warnings": warnings_found,
                    "errors_found": len(errors_found) > 0,
                },
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Text detection failed: {exc}", duration_ms=elapsed)

    def _detect_red_regions(self, img: np.ndarray) -> list[dict]:
        """Detect red-colored regions (common for errors)."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = mask1 | mask2

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 500:
                x, y, w, h = cv2.boundingRect(cnt)
                regions.append({"x": x, "y": y, "width": w, "height": h, "area": int(area)})
        return regions

    def _detect_color_regions(self, img: np.ndarray, color: str) -> list[dict]:
        """Detect specific color regions."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        color_ranges = {
            "orange": ([10, 100, 100], [25, 255, 255]),
            "yellow": ([25, 100, 100], [35, 255, 255]),
            "blue": ([100, 100, 100], [130, 255, 255]),
        }

        if color not in color_ranges:
            return []

        lower, upper = color_ranges[color]
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 300:
                x, y, w, h = cv2.boundingRect(cnt)
                regions.append({"x": x, "y": y, "width": w, "height": h})
        return regions

    def _detect_dialog(self, img: np.ndarray) -> dict | None:
        """Detect dialog/popup windows."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = img.shape[:2]

        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / max(ch, 1)
            area_ratio = (cw * ch) / (w * h)

            if 0.8 < aspect < 2.0 and 0.05 < area_ratio < 0.5:
                return {"x": x, "y": y, "width": cw, "height": ch}

        return None
