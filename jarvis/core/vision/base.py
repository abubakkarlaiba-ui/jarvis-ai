"""
Base types and configuration for the vision system.
=====================================================
Defines shared data structures, enums, and the vision configuration.

Usage:
    config = VisionConfig(camera_enabled=True, ocr_engine="tesseract")
    result = VisionResult(success=True, data={"text": "Hello"})
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class VisionTask(Enum):
    """Types of vision analysis tasks."""
    SCREENSHOT = auto()
    OCR = auto()
    OBJECT_DETECT = auto()
    FACE_DETECT = auto()
    IMAGE_UNDERSTAND = auto()
    PDF_READ = auto()
    UI_RECOGNIZE = auto()
    CHART_ANALYZE = auto()
    ERROR_DETECT = auto()
    SCREEN_MONITOR = auto()
    CAMERA_CAPTURE = auto()


@dataclass
class VisionConfig:
    """Configuration for the vision system."""
    # Camera
    camera_enabled: bool = True
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30

    # Screen
    screen_enabled: bool = True
    screen_monitor_interval: float = 1.0
    screen_capture_dir: str = "./data/screenshots/vision"

    # OCR
    ocr_enabled: bool = True
    ocr_engine: str = "easyocr"  # easyocr, tesseract, paddleocr
    ocr_languages: list[str] = field(default_factory=lambda: ["en"])

    # Object detection
    object_detection_enabled: bool = True
    object_detection_model: str = "yolov8n"
    object_confidence_threshold: float = 0.5

    # Face detection
    face_detection_enabled: bool = True
    face_recognition_enabled: bool = False

    # Image understanding (LLM-based)
    image_understanding_enabled: bool = True
    image_model: str = "gpt-4o"

    # PDF
    pdf_enabled: bool = True
    pdf_max_pages: int = 50

    # UI recognition
    ui_recognition_enabled: bool = True

    # Chart analysis
    chart_analysis_enabled: bool = True

    # Error recognition
    error_recognition_enabled: bool = True

    # Monitoring
    monitor_enabled: bool = True
    monitor_interval: float = 2.0
    monitor_change_threshold: float = 0.1

    # Paths
    models_dir: str = "./data/vision_models"
    cache_dir: str = "./data/vision_cache"

    def to_dict(self) -> dict:
        return {
            "camera_enabled": self.camera_enabled,
            "ocr_engine": self.ocr_engine,
            "ocr_languages": self.ocr_languages,
            "object_model": self.object_detection_model,
            "image_model": self.image_model,
            "monitor_interval": self.monitor_interval,
        }


@dataclass
class VisionResult:
    """Result of a vision operation."""
    success: bool
    message: str = ""
    task: VisionTask | None = None
    data: Any = None
    confidence: float = 0.0
    duration_ms: float = 0.0
    image_path: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "task": self.task.name if self.task else None,
            "confidence": round(self.confidence, 3),
            "duration_ms": round(self.duration_ms, 1),
            "image_path": self.image_path,
            "error": self.error,
        }


@dataclass
class DetectedObject:
    """A detected object in an image."""
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    area: int = 0

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "bbox": list(self.bbox),
            "area": self.area,
        }


@dataclass
class DetectedFace:
    """A detected face in an image."""
    bbox: tuple[int, int, int, int]
    confidence: float = 0.0
    name: str = "unknown"
    age_estimate: int = 0
    emotion: str = ""
    landmarks: list[tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "bbox": list(self.bbox),
            "confidence": round(self.confidence, 3),
            "name": self.name,
            "age_estimate": self.age_estimate,
            "emotion": self.emotion,
            "landmarks_count": len(self.landmarks),
        }


@dataclass
class OCRResult:
    """OCR extraction result."""
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None
    language: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 3),
            "bbox": list(self.bbox) if self.bbox else None,
            "language": self.language,
        }


@dataclass
class UIElement:
    """A recognized UI element."""
    element_type: str  # button, input, link, text, icon, menu, etc.
    label: str
    bbox: tuple[int, int, int, int]
    confidence: float = 0.0
    state: str = ""  # enabled, disabled, focused, etc.
    action: str = ""  # suggested action

    def to_dict(self) -> dict:
        return {
            "element_type": self.element_type,
            "label": self.label,
            "bbox": list(self.bbox),
            "confidence": round(self.confidence, 3),
            "state": self.state,
            "action": self.action,
        }


@dataclass
class ScreenChange:
    """A detected change on screen."""
    timestamp: float
    region: tuple[int, int, int, int]
    change_type: str  # content, layout, text, new_element
    old_hash: str = ""
    new_hash: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "region": list(self.region),
            "change_type": self.change_type,
            "description": self.description,
        }
