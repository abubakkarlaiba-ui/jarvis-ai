"""
Unified vision system for JARVIS.
===================================
Wires together all vision subsystems into a single, cohesive API.

Subsystems:
    - CameraManager — webcam access and capture
    - ScreenAnalyzer — screen capture and analysis
    - OCREngine — text extraction from images
    - ObjectDetector — detect objects in images
    - FaceDetector — face detection
    - ImageUnderstanding — AI-powered image analysis via LLM
    - PDFReader — PDF reading and text extraction
    - UIRecognizer — UI element detection
    - ChartAnalyzer — chart and diagram understanding
    - ErrorRecognizer — error message detection
    - ScreenMonitor — real-time screen monitoring

Usage:
    vision = VisionSystem(settings)
    await vision.initialize()
    await vision.screenshot_analysis()
    await vision.ocr_from_screen()
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

import numpy as np

from jarvis.config.settings import VisionSettings
from jarvis.core.vision.base import VisionConfig, VisionResult
from jarvis.core.vision.camera import CameraManager
from jarvis.core.vision.screen import ScreenAnalyzer
from jarvis.core.vision.ocr import OCREngine
from jarvis.core.vision.object_detection import ObjectDetector
from jarvis.core.vision.face_detection import FaceDetector
from jarvis.core.vision.image_understanding import ImageUnderstanding
from jarvis.core.vision.pdf_reader import PDFReader
from jarvis.core.vision.ui_recognition import UIRecognizer
from jarvis.core.vision.chart_analysis import ChartAnalyzer
from jarvis.core.vision.error_recognition import ErrorRecognizer
from jarvis.core.vision.monitor import ScreenMonitor

logger = logging.getLogger(__name__)


class VisionSystem:
    """Unified vision system for JARVIS.

    Provides a single interface to all vision capabilities.

    Example:
        vision = VisionSystem(settings)
        await vision.initialize()

        # Screen capture
        result = await vision.screenshot()
        frame = result.data["frame"]

        # OCR
        result = await vision.ocr_from_screen()

        # Object detection
        result = await vision.detect_objects(frame)

        # Image understanding
        result = await vision.understand_image(frame)
    """

    def __init__(self, settings: VisionSettings):
        self._settings = settings
        self._config = VisionConfig(
            camera_enabled=settings.camera_enabled,
            camera_index=settings.camera_index,
            camera_width=settings.camera_width,
            camera_height=settings.camera_height,
            camera_fps=settings.camera_fps,
            screen_enabled=settings.screen_capture_enabled,
            screen_monitor_interval=settings.screenshot_interval,
            screen_capture_dir=settings.screenshot_dir,
            ocr_enabled=settings.ocr_enabled,
            ocr_engine=settings.ocr_engine,
            ocr_languages=settings.ocr_languages,
            object_detection_enabled=settings.object_detection_enabled,
            object_detection_model=settings.object_detection_model,
            object_confidence_threshold=settings.object_confidence_threshold,
            face_detection_enabled=settings.face_detection_enabled,
            image_understanding_enabled=settings.image_understanding_enabled,
            image_model=settings.image_understanding_model,
            pdf_enabled=settings.pdf_enabled,
            pdf_max_pages=settings.pdf_max_pages,
            ui_recognition_enabled=settings.ui_recognition_enabled,
            chart_analysis_enabled=settings.chart_analysis_enabled,
            error_recognition_enabled=settings.error_recognition_enabled,
            monitor_enabled=settings.screen_monitor_enabled,
            monitor_interval=settings.screen_monitor_interval,
            models_dir=settings.models_dir,
            cache_dir=settings.cache_dir,
        )

        self.camera: CameraManager | None = None
        self.screen: ScreenAnalyzer | None = None
        self.ocr: OCREngine | None = None
        self.objects: ObjectDetector | None = None
        self.faces: FaceDetector | None = None
        self.understanding: ImageUnderstanding | None = None
        self.pdf: PDFReader | None = None
        self.ui: UIRecognizer | None = None
        self.charts: ChartAnalyzer | None = None
        self.errors: ErrorRecognizer | None = None
        self.monitor: ScreenMonitor | None = None
        self._initialized = False

    async def initialize(self, api_key: str | None = None, base_url: str | None = None) -> VisionResult:
        """Initialize all vision subsystems.

        Args:
            api_key: API key for LLM vision.
            base_url: Optional API base URL.
        """
        if self._initialized:
            return VisionResult(success=True, message="Already initialized")

        logger.info("Initializing vision system...")

        self.camera = CameraManager(self._config)
        self.screen = ScreenAnalyzer(self._config)
        self.ocr = OCREngine(self._config)
        self.objects = ObjectDetector(self._config)
        self.faces = FaceDetector(self._config)
        self.understanding = ImageUnderstanding(self._config, api_key, base_url)
        self.pdf = PDFReader(self._config)
        self.ui = UIRecognizer(self._config)
        self.charts = ChartAnalyzer(self._config)
        self.errors = ErrorRecognizer(self._config)
        self.monitor = ScreenMonitor(self._config)

        await self.ocr.initialize()
        await self.objects.initialize()
        await self.faces.initialize()
        await self.understanding.initialize()
        await self.charts.initialize(api_key, base_url)

        self._initialized = True
        logger.info("Vision system initialized")
        return VisionResult(success=True, message="Vision system initialized")

    async def shutdown(self) -> None:
        """Shut down all vision subsystems."""
        if self.monitor:
            await self.monitor.stop()
        if self.camera:
            await self.camera.shutdown()
        self._initialized = False

    # ──────────────────────────────────────────────
    # Camera shortcuts
    # ──────────────────────────────────────────────

    async def capture_camera(self) -> VisionResult:
        return await self.camera.capture()

    async def save_camera_capture(self, path: str | None = None) -> VisionResult:
        return await self.camera.capture_to_file(path)

    # ──────────────────────────────────────────────
    # Screen shortcuts
    # ──────────────────────────────────────────────

    async def screenshot(self) -> VisionResult:
        return await self.screen.capture_full()

    async def screenshot_region(self, x: int, y: int, w: int, h: int) -> VisionResult:
        return await self.screen.capture_region(x, y, w, h)

    async def save_screenshot(self, name: str | None = None) -> VisionResult:
        return await self.screen.save_screenshot(name=name)

    # ──────────────────────────────────────────────
    # OCR shortcuts
    # ──────────────────────────────────────────────

    async def ocr_from_image(self, image: np.ndarray | str) -> VisionResult:
        return await self.ocr.extract_text(image)

    async def ocr_from_screen(self) -> VisionResult:
        result = await self.screenshot()
        if not result.success:
            return result
        return await self.ocr.extract_text(result.data["frame"])

    async def ocr_find_text(self, image: np.ndarray | str, query: str) -> VisionResult:
        return await self.ocr.find_text(image, query)

    # ──────────────────────────────────────────────
    # Object detection shortcuts
    # ──────────────────────────────────────────────

    async def detect_objects(self, image: np.ndarray | str) -> VisionResult:
        return await self.objects.detect(image)

    async def detect_objects_annotated(self, image: np.ndarray) -> VisionResult:
        return await self.objects.detect_and_draw(image)

    async def count_objects(self, image: np.ndarray) -> VisionResult:
        return await self.objects.count_objects(image)

    # ──────────────────────────────────────────────
    # Face detection shortcuts
    # ──────────────────────────────────────────────

    async def detect_faces(self, image: np.ndarray | str) -> VisionResult:
        return await self.faces.detect(image)

    async def detect_faces_annotated(self, image: np.ndarray) -> VisionResult:
        return await self.faces.detect_and_draw(image)

    async def count_faces(self, image: np.ndarray) -> VisionResult:
        return await self.faces.count_faces(image)

    # ──────────────────────────────────────────────
    # Image understanding shortcuts
    # ──────────────────────────────────────────────

    async def understand_image(self, image: np.ndarray | str, question: str = "") -> VisionResult:
        if question:
            return await self.understanding.ask(image, question)
        return await self.understanding.describe(image)

    async def describe_image(self, image: np.ndarray | str, detail: str = "detailed") -> VisionResult:
        return await self.understanding.describe(image, detail)

    async def extract_text_from_image(self, image: np.ndarray | str) -> VisionResult:
        return await self.understanding.extract_text(image)

    async def analyze_ui_screenshot(self, image: np.ndarray | str) -> VisionResult:
        return await self.understanding.analyze_ui(image)

    async def explain_chart(self, image: np.ndarray | str) -> VisionResult:
        return await self.understanding.explain_chart(image)

    async def explain_diagram(self, image: np.ndarray | str) -> VisionResult:
        return await self.understanding.explain_diagram(image)

    async def detect_image_errors(self, image: np.ndarray | str) -> VisionResult:
        return await self.understanding.detect_errors(image)

    # ──────────────────────────────────────────────
    # PDF shortcuts
    # ──────────────────────────────────────────────

    async def read_pdf(self, path: str, max_pages: int | None = None) -> VisionResult:
        return await self.pdf.extract_text(path, max_pages)

    async def render_pdf_page(self, path: str, page: int = 1) -> VisionResult:
        return await self.pdf.render_page(path, page)

    async def get_pdf_metadata(self, path: str) -> VisionResult:
        return await self.pdf.get_metadata(path)

    # ──────────────────────────────────────────────
    # UI recognition shortcuts
    # ──────────────────────────────────────────────

    async def detect_ui_elements(self, image: np.ndarray | str) -> VisionResult:
        return await self.ui.detect_elements(image)

    async def find_ui_button(self, image: np.ndarray, label: str = "") -> VisionResult:
        return await self.ui.find_element(image, "button", label)

    # ──────────────────────────────────────────────
    # Error detection shortcuts
    # ──────────────────────────────────────────────

    async def detect_errors(self, image: np.ndarray | str) -> VisionResult:
        return await self.errors.detect(image)

    async def find_error_text(self, image: np.ndarray | str) -> VisionResult:
        return await self.errors.find_error_text(image)

    # ──────────────────────────────────────────────
    # Screen monitoring shortcuts
    # ──────────────────────────────────────────────

    async def start_monitoring(
        self,
        callback: Callable | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> VisionResult:
        return await self.monitor.start(callback=callback, region=region)

    async def stop_monitoring(self) -> VisionResult:
        return await self.monitor.stop()

    def get_monitor_changes(self) -> list[dict]:
        return self.monitor.get_changes()

    # ──────────────────────────────────────────────
    # Combined analysis
    # ──────────────────────────────────────────────

    async def full_screen_analysis(self) -> VisionResult:
        """Perform a comprehensive analysis of the current screen."""
        import time
        start = time.perf_counter()

        screen_result = await self.screenshot()
        if not screen_result.success:
            return screen_result

        frame = screen_result.data["frame"]

        ocr_result = await self.ocr_from_image(frame)
        face_result = await self.detect_faces(frame)
        error_result = await self.detect_errors(frame)
        ui_result = await self.detect_ui_elements(frame)

        elapsed = (time.perf_counter() - start) * 1000
        return VisionResult(
            success=True,
            message="Full screen analysis complete",
            data={
                "ocr": ocr_result.data if ocr_result.success else None,
                "faces": face_result.data if face_result.success else None,
                "errors": error_result.data if error_result.success else None,
                "ui_elements": ui_result.data if ui_result.success else None,
                "dimensions": {"width": frame.shape[1], "height": frame.shape[0]},
            },
            duration_ms=elapsed,
        )
