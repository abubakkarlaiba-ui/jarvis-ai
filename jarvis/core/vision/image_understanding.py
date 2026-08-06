"""
Image understanding for JARVIS vision system.
===============================================
AI-powered image analysis using LLM vision capabilities.

Supports:
    - Image description
    - Visual question answering
    - Scene analysis
    - Text extraction from images
    - Object identification
    - Chart/diagram explanation

Usage:
    understanding = ImageUnderstanding(config)
    result = await understanding.describe(image)
    result = await understanding.ask(image, "What is in this image?")
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask

logger = logging.getLogger(__name__)


class ImageUnderstanding:
    """AI-powered image analysis using LLM vision.

    Example:
        config = VisionConfig(image_model="gpt-4o")
        understanding = ImageUnderstanding(config)
        result = await understanding.describe(frame)
        answer = await understanding.ask(frame, "What text is visible?")
    """

    def __init__(self, config: VisionConfig, api_key: str | None = None, base_url: str | None = None):
        self._config = config
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any = None

    async def initialize(self) -> VisionResult:
        """Initialize the LLM vision client."""
        if not self._config.image_understanding_enabled:
            return VisionResult(success=False, message="Image understanding disabled")

        try:
            if self._api_key:
                from openai import AsyncOpenAI
                kwargs = {"api_key": self._api_key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = AsyncOpenAI(**kwargs)
            else:
                return VisionResult(
                    success=False,
                    message="No API key for image understanding. Set image_api_key in config.",
                )

            return VisionResult(
                success=True,
                message=f"Image understanding initialized: {self._config.image_model}",
                task=VisionTask.IMAGE_UNDERSTAND,
            )

        except ImportError:
            return VisionResult(success=False, message="openai not installed: pip install openai")
        except Exception as exc:
            return VisionResult(success=False, message=f"Init failed: {exc}", error=str(exc))

    def _frame_to_base64(self, frame: np.ndarray, format: str = ".jpg") -> str:
        """Convert frame to base64 string."""
        _, buffer = cv2.imencode(format, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode("utf-8")

    async def _analyze_image(
        self,
        image: np.ndarray | str,
        prompt: str,
        max_tokens: int = 1000,
    ) -> VisionResult:
        """Send image to LLM for analysis.

        Args:
            image: numpy array or file path.
            prompt: Analysis prompt.
            max_tokens: Maximum response tokens.

        Returns:
            VisionResult with analysis.
        """
        start = time.perf_counter()

        if not self._client:
            return VisionResult(success=False, message="Vision client not initialized. Call initialize() first.")

        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read: {image}")
            else:
                img = image

            b64_image = self._frame_to_base64(img)

            response = await self._client.chat.completions.create(
                model=self._config.image_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=max_tokens,
            )

            analysis = response.choices[0].message.content
            elapsed = (time.perf_counter() - start) * 1000

            return VisionResult(
                success=True,
                message=f"Image analyzed ({len(analysis)} chars)",
                task=VisionTask.IMAGE_UNDERSTAND,
                data={"analysis": analysis, "model": self._config.image_model},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Image analysis failed: %s", exc)
            return VisionResult(success=False, message=f"Analysis failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def describe(self, image: np.ndarray | str, detail: str = "detailed") -> VisionResult:
        """Describe an image in detail.

        Args:
            image: Image to describe.
            detail: "brief", "detailed", or "comprehensive".
        """
        prompts = {
            "brief": "Describe this image in 1-2 sentences.",
            "detailed": "Describe this image in detail. Include objects, people, setting, colors, and any text visible.",
            "comprehensive": "Provide a comprehensive analysis of this image. Include:\n1. Overall scene description\n2. Objects and their positions\n3. People (if any) and their actions\n4. Text visible in the image\n5. Colors and lighting\n6. Any notable details",
        }
        prompt = prompts.get(detail, prompts["detailed"])
        return await self._analyze_image(image, prompt)

    async def ask(self, image: np.ndarray | str, question: str) -> VisionResult:
        """Ask a question about an image.

        Args:
            image: Image to analyze.
            question: Question about the image.
        """
        return await self._analyze_image(image, f"Answer this question about the image: {question}")

    async def extract_text(self, image: np.ndarray | str) -> VisionResult:
        """Extract all visible text from an image using LLM vision."""
        prompt = "Extract ALL text visible in this image. Return the text exactly as it appears, preserving formatting and line breaks. If no text is visible, say 'No text found'."
        return await self._analyze_image(image, prompt, max_tokens=2000)

    async def identify_objects(self, image: np.ndarray | str) -> VisionResult:
        """Identify and list all objects in an image."""
        prompt = """List all objects visible in this image as a JSON array.
Each object should have: label, position (brief location), size (small/medium/large).
Example: [{"label": "laptop", "position": "center desk", "size": "medium"}]
Return only the JSON array."""
        return await self._analyze_image(image, prompt)

    async def analyze_ui(self, image: np.ndarray | str) -> VisionResult:
        """Analyze a UI screenshot for elements and layout."""
        prompt = """Analyze this UI screenshot. Identify:
1. Application name and type
2. UI elements (buttons, inputs, menus, tabs, etc.)
3. Current state (what's displayed, selected, active)
4. Layout structure
5. Any error messages or notifications
Provide a structured analysis."""
        return await self._analyze_image(image, prompt)

    async def explain_chart(self, image: np.ndarray | str) -> VisionResult:
        """Explain a chart or graph."""
        prompt = """Analyze this chart/graph:
1. Type of chart (bar, line, pie, scatter, etc.)
2. Title and labels
3. Key data points and trends
4. Notable patterns or outliers
5. Summary of what the chart shows
Provide a clear explanation suitable for someone who can't see the image."""
        return await self._analyze_image(image, prompt)

    async def explain_diagram(self, image: np.ndarray | str) -> VisionResult:
        """Explain a diagram or flowchart."""
        prompt = """Explain this diagram/flowchart:
1. Type of diagram (flowchart, architecture, network, etc.)
2. Main components and their relationships
3. Flow or process depicted
4. Key connections and dependencies
5. Overall purpose and meaning
Explain it as if describing to someone who cannot see it."""
        return await self._analyze_image(image, prompt)

    async def detect_errors(self, image: np.ndarray | str) -> VisionResult:
        """Detect error messages or异常 states in a screenshot."""
        prompt = """Check this screenshot for any error messages, warnings, or异常 states:
1. Error dialogs or popups
2. Error text in the UI
3. Warning indicators (red/yellow highlights)
4. Failed operations or broken elements
5. Any text indicating an error condition
Report what you find, or say 'No errors detected' if the screen looks normal."""
        return await self._analyze_image(image, prompt)

    async def compare_images(self, image1: np.ndarray | str, image2: np.ndarray | str, question: str = "") -> VisionResult:
        """Compare two images."""
        start = time.perf_counter()

        if not self._client:
            return VisionResult(success=False, message="Vision client not initialized")

        try:
            if isinstance(image1, str):
                img1 = cv2.imread(image1)
            else:
                img1 = image1

            if isinstance(image2, str):
                img2 = cv2.imread(image2)
            else:
                img2 = image2

            b64_1 = self._frame_to_base64(img1)
            b64_2 = self._frame_to_base64(img2)

            prompt = question or "Compare these two images. What are the similarities and differences?"

            response = await self._client.chat.completions.create(
                model=self._config.image_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_1}", "detail": "high"}},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_2}", "detail": "high"}},
                        ],
                    }
                ],
                max_tokens=1500,
            )

            analysis = response.choices[0].message.content
            elapsed = (time.perf_counter() - start) * 1000

            return VisionResult(
                success=True,
                message="Images compared",
                data={"comparison": analysis},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Comparison failed: {exc}", duration_ms=elapsed)
