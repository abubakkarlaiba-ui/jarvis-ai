"""
Object detection for JARVIS vision system.
============================================
Detect and classify objects in images using YOLO or similar models.

Supports:
    - YOLOv8 object detection
    - Custom model loading
    - Real-time detection
    - Object tracking

Usage:
    detector = ObjectDetector(config)
    await detector.initialize()
    result = await detector.detect(image)
    for obj in result.data:
        print(f"{obj['label']}: {obj['confidence']:.1%}")
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask, DetectedObject

logger = logging.getLogger(__name__)


class ObjectDetector:
    """Detect objects in images using YOLO.

    Example:
        config = VisionConfig(object_detection_model="yolov8n")
        detector = ObjectDetector(config)
        await detector.initialize()
        result = await detector.detect(frame)
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._model: Any = None
        self._initialized = False

    async def initialize(self) -> VisionResult:
        """Initialize the object detection model."""
        if not self._config.object_detection_enabled:
            return VisionResult(success=False, message="Object detection disabled")

        try:
            from ultralytics import YOLO

            model_name = self._config.object_detection_model
            models_dir = Path(self._config.models_dir)
            models_dir.mkdir(parents=True, exist_ok=True)

            self._model = YOLO(model_name)
            self._initialized = True

            return VisionResult(
                success=True,
                message=f"Object detection initialized: {model_name}",
                task=VisionTask.OBJECT_DETECT,
            )

        except ImportError:
            return VisionResult(
                success=False,
                message="ultralytics not installed: pip install ultralytics",
            )
        except Exception as exc:
            return VisionResult(success=False, message=f"Object detection init failed: {exc}", error=str(exc))

    async def detect(
        self,
        image: np.ndarray | str,
        confidence: float | None = None,
        classes: list[int] | None = None,
    ) -> VisionResult:
        """Detect objects in an image.

        Args:
            image: numpy array or file path.
            confidence: Confidence threshold override.
            classes: Filter by class IDs.

        Returns:
            VisionResult with list of DetectedObject dicts.
        """
        start = time.perf_counter()
        if not self._initialized:
            return VisionResult(success=False, message="Object detector not initialized")

        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read image: {image}")
            else:
                img = image

            conf = confidence or self._config.object_confidence_threshold
            results = self._model.predict(
                img,
                conf=conf,
                classes=classes,
                verbose=False,
            )

            detected = []
            if results and len(results) > 0:
                for r in results:
                    boxes = r.boxes
                    if boxes is not None:
                        for box in boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            conf_val = float(box.conf[0])
                            cls_id = int(box.cls[0])
                            label = r.names.get(cls_id, f"class_{cls_id}")

                            area = (x2 - x1) * (y2 - y1)
                            detected.append(DetectedObject(
                                label=label,
                                confidence=conf_val,
                                bbox=(x1, y1, x2, y2),
                                area=area,
                            ))

            elapsed = (time.perf_counter() - start) * 1000
            avg_conf = sum(d.confidence for d in detected) / max(len(detected), 1)

            return VisionResult(
                success=True,
                message=f"Detected {len(detected)} objects",
                task=VisionTask.OBJECT_DETECT,
                data=[d.to_dict() for d in detected],
                confidence=avg_conf,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Object detection failed: %s", exc)
            return VisionResult(success=False, message=f"Detection failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def detect_and_draw(self, image: np.ndarray, confidence: float | None = None) -> VisionResult:
        """Detect objects and draw bounding boxes on the image."""
        det_result = await self.detect(image, confidence)
        if not det_result.success:
            return det_result

        try:
            annotated = image.copy()
            colors = [
                (255, 0, 0), (0, 255, 0), (0, 0, 255),
                (255, 255, 0), (255, 0, 255), (0, 255, 255),
            ]

            for i, obj in enumerate(det_result.data):
                x1, y1, x2, y2 = obj["bbox"]
                color = colors[i % len(colors)]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                label = f"{obj['label']}: {obj['confidence']:.1%}"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(annotated, (x1, y1 - h - 10), (x1 + w, y1), color, -1)
                cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            det_result.data = {"frame": annotated, "detections": det_result.data}
            det_result.message = f"Drew {len(det_result.data)} bounding boxes"
            return det_result

        except Exception as exc:
            return VisionResult(success=False, message=f"Draw failed: {exc}")

    async def count_objects(self, image: np.ndarray) -> VisionResult:
        """Count objects by class in an image."""
        det_result = await self.detect(image)
        if not det_result.success:
            return det_result

        counts: dict[str, int] = {}
        for obj in det_result.data:
            label = obj["label"]
            counts[label] = counts.get(label, 0) + 1

        return VisionResult(
            success=True,
            message=f"Found {sum(counts.values())} objects in {len(counts)} classes",
            task=VisionTask.OBJECT_DETECT,
            data={"counts": counts, "total": sum(counts.values())},
        )
