"""
AI vision module for JARVIS.
=============================
Camera, screen analysis, OCR, object/face detection, image understanding,
PDF reading, UI recognition, chart analysis, and real-time monitoring.

Quick Start:
    from jarvis.core.vision import VisionSystem
    vision = VisionSystem(settings)
    await vision.initialize()
    await vision.screenshot_analysis()
    await vision.ocr_from_screen()
"""

from jarvis.core.vision.vision import VisionSystem
from jarvis.core.vision.base import VisionConfig, VisionResult, DetectedObject, DetectedFace
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

__all__ = [
    "VisionSystem",
    "VisionConfig",
    "VisionResult",
    "DetectedObject",
    "DetectedFace",
    "CameraManager",
    "ScreenAnalyzer",
    "OCREngine",
    "ObjectDetector",
    "FaceDetector",
    "ImageUnderstanding",
    "PDFReader",
    "UIRecognizer",
    "ChartAnalyzer",
    "ErrorRecognizer",
    "ScreenMonitor",
]
