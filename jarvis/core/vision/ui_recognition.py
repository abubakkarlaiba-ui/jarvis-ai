"""
UI element recognition for JARVIS vision system.
==================================================
Detect and classify UI elements in screenshots.

Supports:
    - Button detection
    - Input field detection
    - Text element detection
    - Icon detection
    - Menu detection
    - Layout analysis

Usage:
    ui = UIRecognizer(config)
    result = await ui.detect_elements(screenshot)
    result = await ui.find_button(screenshot, "Submit")
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask, UIElement

logger = logging.getLogger(__name__)


class UIRecognizer:
    """Recognize and classify UI elements in screenshots.

    Example:
        config = VisionConfig(ui_recognition_enabled=True)
        ui = UIRecognizer(config)
        result = await ui.detect_elements(screenshot)
        for elem in result.data:
            print(f"{elem['element_type']}: {elem['label']}")
    """

    def __init__(self, config: VisionConfig):
        self._config = config

    async def detect_elements(self, image: np.ndarray | str) -> VisionResult:
        """Detect UI elements in a screenshot.

        Uses image processing to identify common UI patterns:
        - Rectangular regions (buttons, inputs, cards)
        - Text regions (labels, headings)
        - Icon-like regions (small, square)

        Args:
            image: Screenshot as numpy array or file path.

        Returns:
            VisionResult with list of UIElement dicts.
        """
        start = time.perf_counter()
        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read: {image}")
            else:
                img = image

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            elements = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h

                if area < 200 or area > img.shape[0] * img.shape[1] * 0.5:
                    continue

                aspect = w / max(h, 1)
                roi = img[y:y + h, x:x + w]
                mean_color = cv2.mean(roi)[:3]

                elem_type = self._classify_element(w, h, aspect, mean_color, gray[y:y + h, x:x + w])

                if elem_type:
                    elements.append(UIElement(
                        element_type=elem_type,
                        label="",
                        bbox=(x, y, x + w, y + h),
                        confidence=0.6,
                    ))

            elements = self._merge_overlapping(elements)

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Detected {len(elements)} UI elements",
                task=VisionTask.UI_RECOGNIZE,
                data=[e.to_dict() for e in elements],
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"UI detection failed: {exc}", duration_ms=elapsed)

    def _classify_element(
        self,
        w: int,
        h: int,
        aspect: float,
        mean_color: tuple,
        roi_gray: np.ndarray,
    ) -> str | None:
        """Classify a UI element based on its properties."""
        if 2.5 < aspect < 8 and 20 < h < 80:
            return "button"
        if 1.5 < aspect < 6 and 15 < h < 60:
            return "input"
        if 0.8 < aspect < 1.2 and 10 < w < 80:
            return "icon"
        if 3 < aspect and h < 30:
            return "text"
        if aspect > 4 and h > 40:
            return "card"
        if 1.5 < aspect < 3 and 30 < h < 150:
            return "container"
        return None

    def _merge_overlapping(self, elements: list[UIElement], iou_threshold: float = 0.5) -> list[UIElement]:
        """Merge overlapping UI elements."""
        if not elements:
            return elements

        sorted_elems = sorted(elements, key=lambda e: e.bbox[2] * e.bbox[3], reverse=True)
        merged = []

        for elem in sorted_elems:
            overlap = False
            for existing in merged:
                iou = self._calculate_iou(elem.bbox, existing.bbox)
                if iou > iou_threshold:
                    overlap = True
                    break
            if not overlap:
                merged.append(elem)

        return merged

    @staticmethod
    def _calculate_iou(bbox1: tuple, bbox2: tuple) -> float:
        """Calculate Intersection over Union."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection

        return intersection / max(union, 1)

    async def find_element(
        self,
        image: np.ndarray,
        element_type: str,
        label: str = "",
    ) -> VisionResult:
        """Find a specific type of UI element."""
        det_result = await self.detect_elements(image)
        if not det_result.success:
            return det_result

        matches = [
            e for e in det_result.data
            if e["element_type"] == element_type
        ]

        if label:
            matches = [e for e in matches if label.lower() in e.get("label", "").lower()]

        return VisionResult(
            success=True,
            message=f"Found {len(matches)} {element_type} elements",
            data=matches,
        )

    async def draw_elements(self, image: np.ndarray, elements: list[dict] | None = None) -> VisionResult:
        """Draw detected UI elements on an image."""
        if elements is None:
            det_result = await self.detect_elements(image)
            if not det_result.success:
                return det_result
            elements = det_result.data

        try:
            annotated = image.copy()
            colors = {
                "button": (0, 255, 0),
                "input": (255, 0, 0),
                "icon": (0, 0, 255),
                "text": (255, 255, 0),
                "card": (255, 0, 255),
                "container": (0, 255, 255),
            }

            for elem in elements:
                x1, y1, x2, y2 = elem["bbox"]
                color = colors.get(elem["element_type"], (128, 128, 128))
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                label = f"{elem['element_type']}"
                cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            return VisionResult(
                success=True,
                message=f"Drew {len(elements)} elements",
                data={"frame": annotated},
            )

        except Exception as exc:
            return VisionResult(success=False, message=f"Draw failed: {exc}")
