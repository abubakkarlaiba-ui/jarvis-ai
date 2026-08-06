"""
Chart analysis for JARVIS vision system.
==========================================
Analyze and explain charts, graphs, and data visualizations.

Supports:
    - Chart type detection (bar, line, pie, scatter, etc.)
    - Data extraction from charts
    - Trend analysis
    - Value reading

Usage:
    chart = ChartAnalyzer(config)
    result = await chart.analyze(screenshot)
    result = await chart.get_chart_type(screenshot)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask

logger = logging.getLogger(__name__)


class ChartAnalyzer:
    """Analyze charts and data visualizations.

    Example:
        config = VisionConfig(chart_analysis_enabled=True)
        analyzer = ChartAnalyzer(config)
        result = await analyzer.analyze(chart_image)
        print(result.data["chart_type"])
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._llm_client: Any = None

    async def initialize(self, api_key: str | None = None, base_url: str | None = None) -> VisionResult:
        """Initialize with optional LLM client for advanced analysis."""
        if api_key:
            try:
                from openai import AsyncOpenAI
                kwargs = {"api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                self._llm_client = AsyncOpenAI(**kwargs)
                return VisionResult(success=True, message="Chart analyzer initialized with LLM")
            except Exception as exc:
                logger.debug("LLM init failed: %s", exc)

        return VisionResult(success=True, message="Chart analyzer initialized (basic mode)")

    async def analyze(self, image: np.ndarray | str) -> VisionResult:
        """Analyze a chart image.

        Args:
            image: Chart screenshot as numpy array or file path.

        Returns:
            VisionResult with chart analysis.
        """
        start = time.perf_counter()
        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read: {image}")
            else:
                img = image

            chart_info = self._detect_chart_type(img)
            colors = self._extract_dominant_colors(img)
            layout = self._analyze_layout(img)

            analysis = {
                "chart_type": chart_info["type"],
                "confidence": chart_info["confidence"],
                "colors": colors,
                "layout": layout,
                "dimensions": {"width": img.shape[1], "height": img.shape[0]},
            }

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Chart type: {analysis['chart_type']}",
                task=VisionTask.CHART_ANALYZE,
                data=analysis,
                confidence=chart_info["confidence"],
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Chart analysis failed: {exc}", duration_ms=elapsed)

    def _detect_chart_type(self, img: np.ndarray) -> dict:
        """Detect the type of chart based on visual features."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        h, w = img.shape[:2]
        aspect = w / max(h, 1)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rectangular_count = 0
        circular_count = 0

        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
            if len(approx) == 4:
                rectangular_count += 1
            elif len(approx) > 8:
                circular_count += 1

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        unique_hues = len(np.unique(hsv[:, :, 0]))

        if unique_hues > 10 and circular_count > 0:
            return {"type": "pie", "confidence": 0.6}
        elif rectangular_count > 5:
            return {"type": "bar", "confidence": 0.7}
        elif rectangular_count > 2 and aspect > 1.2:
            return {"type": "line", "confidence": 0.5}

        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=50, maxLineGap=10)
        if lines is not None and len(lines) > 5:
            horizontal = sum(1 for l in lines if abs(l[0][1] - l[0][3]) < 10)
            if horizontal > 3:
                return {"type": "bar", "confidence": 0.6}

        return {"type": "unknown", "confidence": 0.3}

    def _extract_dominant_colors(self, img: np.ndarray, n_colors: int = 5) -> list[dict]:
        """Extract dominant colors from the chart."""
        pixels = img.reshape(-1, 3).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(pixels, n_colors, None, criteria, 10, cv2.KMEANS_RANDOM)
        centers = centers.astype(int)

        color_counts = np.bincount(labels.flatten())
        total = len(labels)

        colors = []
        for i in np.argsort(color_counts)[::-1]:
            r, g, b = centers[i]
            colors.append({
                "rgb": [int(r), int(g), int(b)],
                "hex": f"#{int(r):02x}{int(g):02x}{int(b):02x}",
                "percentage": round(color_counts[i] / total * 100, 1),
            })

        return colors

    def _analyze_layout(self, img: np.ndarray) -> dict:
        """Analyze the layout of the chart."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=50, maxLineGap=10)

        has_axes = False
        has_legend = False
        has_title = False

        h, w = img.shape[:2]

        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if y1 > h * 0.8 and abs(y2 - y1) < 5:
                    has_axes = True
                if x1 < w * 0.1 and abs(x2 - x1) < 5:
                    has_axes = True

        top_region = gray[:int(h * 0.15), :]
        if np.mean(top_region) < 200:
            has_title = True

        right_region = gray[:, int(w * 0.75):]
        if np.std(right_region) > 30:
            has_legend = True

        return {
            "has_axes": has_axes,
            "has_legend": has_legend,
            "has_title": has_title,
        }

    async def explain_with_llm(self, image: np.ndarray | str) -> VisionResult:
        """Use LLM to explain the chart in detail."""
        if not self._llm_client:
            return VisionResult(success=False, message="LLM client not initialized")

        import base64
        if isinstance(image, str):
            img = cv2.imread(image)
        else:
            img = image

        _, buffer = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buffer).decode()

        try:
            response = await self._llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this chart in detail. Describe the chart type, data trends, key values, and any notable patterns."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
                    ],
                }],
                max_tokens=1500,
            )

            return VisionResult(
                success=True,
                message="Chart explained via LLM",
                data={"explanation": response.choices[0].message.content},
            )
        except Exception as exc:
            return VisionResult(success=False, message=f"LLM explanation failed: {exc}")
