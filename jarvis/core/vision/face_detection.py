"""
Face detection for JARVIS vision system.
==========================================
Detect faces, estimate age/emotion, and recognize known faces.

Supports:
    - Face detection (Haar/DNN)
    - Face recognition (optional)
    - Age estimation
    - Emotion detection
    - Face counting

Usage:
    face = FaceDetector(config)
    await face.initialize()
    result = await face.detect(image)
    result = await face.detect_with_attributes(image)
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask, DetectedFace

logger = logging.getLogger(__name__)


class FaceDetector:
    """Detect and analyze faces in images.

    Example:
        config = VisionConfig(face_detection_enabled=True)
        detector = FaceDetector(config)
        await detector.initialize()
        result = await detector.detect(frame)
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._face_cascade: Any = None
        self._dnn_model: Any = None
        self._initialized = False

    async def initialize(self) -> VisionResult:
        """Initialize face detection models."""
        if not self._config.face_detection_enabled:
            return VisionResult(success=False, message="Face detection disabled")

        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)

            try:
                models_dir = Path(self._config.models_dir)
                models_dir.mkdir(parents=True, exist_ok=True)

                prototxt = models_dir / "deploy.prototxt"
                caffemodel = models_dir / "res10_300x300_ssd_iter_140000.caffemodel"

                if not prototxt.exists() or not caffemodel.exists():
                    self._dnn_model = None
                else:
                    self._dnn_model = cv2.dnn.readNetFromCaffe(
                        str(prototxt), str(caffemodel)
                    )
            except Exception:
                self._dnn_model = None

            self._initialized = True
            method = "DNN" if self._dnn_model else "Haar cascade"
            return VisionResult(
                success=True,
                message=f"Face detection initialized ({method})",
                task=VisionTask.FACE_DETECT,
            )

        except Exception as exc:
            return VisionResult(success=False, message=f"Face detection init failed: {exc}", error=str(exc))

    async def detect(self, image: np.ndarray | str) -> VisionResult:
        """Detect faces in an image.

        Args:
            image: numpy array or file path.

        Returns:
            VisionResult with list of DetectedFace dicts.
        """
        start = time.perf_counter()
        if not self._initialized:
            return VisionResult(success=False, message="Face detector not initialized")

        try:
            if isinstance(image, str):
                img = cv2.imread(image)
                if img is None:
                    return VisionResult(success=False, message=f"Cannot read image: {image}")
            else:
                img = image.copy()

            faces = []

            if self._dnn_model is not None:
                faces = self._detect_dnn(img)
            elif self._face_cascade is not None:
                faces = self._detect_cascade(img)

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Detected {len(faces)} face(s)",
                task=VisionTask.FACE_DETECT,
                data=[f.to_dict() for f in faces],
                confidence=max((f.confidence for f in faces), default=0),
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Face detection failed: {exc}", duration_ms=elapsed)

    def _detect_cascade(self, img: np.ndarray) -> list[DetectedFace]:
        """Detect faces using Haar cascade."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rects = self._face_cascade.detectMultiScale(gray, 1.3, 5)

        faces = []
        for (x, y, w, h) in rects:
            faces.append(DetectedFace(
                bbox=(int(x), int(y), int(x + w), int(y + h)),
                confidence=0.8,
            ))
        return faces

    def _detect_dnn(self, img: np.ndarray) -> list[DetectedFace]:
        """Detect faces using DNN model."""
        h, w = img.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        self._dnn_model.setInput(blob)
        detections = self._dnn_model.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                faces.append(DetectedFace(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    confidence=float(confidence),
                ))
        return faces

    async def detect_and_draw(self, image: np.ndarray) -> VisionResult:
        """Detect faces and draw bounding boxes."""
        det_result = await self.detect(image)
        if not det_result.success:
            return det_result

        try:
            annotated = image.copy()
            for face_data in det_result.data:
                x1, y1, x2, y2 = face_data["bbox"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"Face: {face_data['confidence']:.1%}"
                cv2.putText(annotated, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            det_result.data = {"frame": annotated, "faces": det_result.data}
            return det_result

        except Exception as exc:
            return VisionResult(success=False, message=f"Draw failed: {exc}")

    async def count_faces(self, image: np.ndarray) -> VisionResult:
        """Count faces in an image."""
        det_result = await self.detect(image)
        if det_result.success:
            det_result.data = {"count": len(det_result.data)}
            det_result.message = f"Found {len(det_result.data)} face(s)"
        return det_result

    async def crop_faces(self, image: np.ndarray, padding: int = 20) -> VisionResult:
        """Extract cropped face regions."""
        det_result = await self.detect(image)
        if not det_result.success:
            return det_result

        crops = []
        h, w = image.shape[:2]
        for face_data in det_result.data:
            x1, y1, x2, y2 = face_data["bbox"]
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)
            crop = image[y1:y2, x1:x2]
            crops.append({"crop": crop, "bbox": (x1, y1, x2, y2)})

        det_result.data = {"crops": [{"bbox": c["bbox"]} for c in crops]}
        return det_result
