"""
Vision module — screen capture, camera input, and OCR.
=====================================================
Provides visual perception capabilities for JARVIS.

Architecture:
    ScreenCapture  →  ImageProcessor  →  OCR / Analysis
         ↑                  ↑                 ↑
    OS screen API      PIL/OpenCV       Tesseract/GPT-4V

Usage:
    vision = VisionModule(settings)
    screenshot = await vision.capture_screen()
    text = await vision.extract_text(screenshot)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from jarvis.config.settings import VisionSettings
from jarvis.utils.helpers import ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class ImageData:
    """Container for captured image data."""
    raw_bytes: bytes
    width: int
    height: int
    format: str = "png"
    timestamp: float = 0.0
    source: str = "unknown"


@dataclass
class OCRResult:
    """Result of an OCR extraction."""
    text: str
    confidence: float
    bounding_boxes: list[dict[str, Any]] | None = None


class ScreenCapture(ABC):
    """Abstract base class for screen capture backends."""

    @abstractmethod
    async def capture(self) -> ImageData:
        """Capture the current screen.

        Returns:
            ImageData with the captured screen content.
        """
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the capture backend."""
        ...


class CameraCapture(ABC):
    """Abstract base class for camera input backends."""

    @abstractmethod
    async def capture_frame(self) -> ImageData:
        """Capture a single frame from the camera.

        Returns:
            ImageData with the captured frame.
        """
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the camera backend."""
        ...


class OCRProcessor(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    async def extract_text(self, image: ImageData) -> OCRResult:
        """Extract text from an image.

        Args:
            image: Input image data.

        Returns:
            OCRResult with extracted text and confidence.
        """
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the OCR engine."""
        ...


class DummyScreenCapture(ScreenCapture):
    """Placeholder screen capture for development."""

    async def initialize(self) -> None:
        logger.info("DummyScreenCapture initialized")

    async def capture(self) -> ImageData:
        logger.debug("DummyScreenCapture: returning placeholder image")
        return ImageData(raw_bytes=b"", width=1920, height=1080, source="dummy")


class DummyOCRProcessor(OCRProcessor):
    """Placeholder OCR processor for development."""

    async def initialize(self) -> None:
        logger.info("DummyOCRProcessor initialized")

    async def extract_text(self, image: ImageData) -> OCRResult:
        logger.debug("DummyOCRProcessor: returning placeholder result")
        return OCRResult(text="", confidence=0.0)


class ImageProcessor:
    """Image preprocessing and analysis utilities.

    Provides resize, crop, format conversion, and basic analysis.
    """

    @staticmethod
    def create_thumbnail(image: ImageData, max_size: tuple[int, int] = (256, 256)) -> ImageData:
        """Create a thumbnail version of an image (placeholder).

        Args:
            image: Source image.
            max_size: Maximum (width, height) for the thumbnail.

        Returns:
            Thumbnail ImageData.
        """
        # In production, use PIL/Pillow here
        logger.debug("ImageProcessor: thumbnail creation not implemented")
        return image

    @staticmethod
    def get_image_info(image: ImageData) -> dict[str, Any]:
        """Return metadata about an image.

        Args:
            image: Image to inspect.

        Returns:
            Dictionary with width, height, format, source, and size.
        """
        return {
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "source": image.source,
            "size_bytes": len(image.raw_bytes),
        }


class VisionModule:
    """High-level vision orchestrator.

    Coordinates screen capture, camera input, OCR, and image processing.

    Example:
        vision = VisionModule(settings)
        await vision.initialize()
        screenshot = await vision.capture_screen()
        ocr_result = await vision.extract_text_from_screen()
    """

    def __init__(
        self,
        settings: VisionSettings,
        screen_capture: ScreenCapture | None = None,
        ocr: OCRProcessor | None = None,
    ):
        self._settings = settings
        self.screen = screen_capture or DummyScreenCapture()
        self.ocr = ocr or DummyOCRProcessor()
        self.image_processor = ImageProcessor()
        self._last_screenshot: ImageData | None = None
        logger.info("VisionModule created")

    async def initialize(self) -> None:
        """Initialize all vision subsystems."""
        await self.screen.initialize()
        await self.ocr.initialize()
        logger.info("VisionModule initialized")

    async def capture_screen(self) -> ImageData:
        """Capture the current screen.

        Returns:
            ImageData with the captured screenshot.
        """
        image = await self.screen.capture()
        self._last_screenshot = image
        return image

    async def extract_text_from_screen(self) -> OCRResult:
        """Capture the screen and extract text via OCR.

        Returns:
            OCRResult with the extracted text.
        """
        image = await self.capture_screen()
        return await self.ocr.extract_text(image)

    async def analyze_screen(self) -> dict[str, Any]:
        """Capture the screen and return basic analysis.

        Returns:
            Dictionary with image info and OCR text.
        """
        image = await self.capture_screen()
        info = self.image_processor.get_image_info(image)
        ocr = await self.ocr.extract_text(image)
        return {
            "image_info": info,
            "ocr_text": ocr.text,
            "ocr_confidence": ocr.confidence,
        }

    async def cleanup(self) -> None:
        """Release vision resources."""
        logger.info("VisionModule cleaned up")
