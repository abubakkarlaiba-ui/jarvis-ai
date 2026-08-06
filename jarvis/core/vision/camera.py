"""
Camera manager for JARVIS vision system.
==========================================
Webcam access, capture, and video stream handling.

Supports:
    - Single/multi camera access
    - Photo capture (single frame)
    - Video recording
    - Camera enumeration
    - Resolution/FPS control

Usage:
    camera = CameraManager(config)
    await camera.initialize()
    frame = await camera.capture()
    cameras = await camera.list_cameras()
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask

logger = logging.getLogger(__name__)


class CameraManager:
    """Manage webcam access and image capture.

    Example:
        config = VisionConfig(camera_index=0)
        camera = CameraManager(config)
        await camera.initialize()
        frame = await camera.capture()
        await camera.save_frame(frame, "capture.jpg")
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._capture: cv2.VideoCapture | None = None
        self._initialized = False
        self._frame: np.ndarray | None = None

    async def initialize(self) -> VisionResult:
        """Initialize the camera."""
        if not self._config.camera_enabled:
            return VisionResult(success=False, message="Camera disabled in config")

        try:
            self._capture = cv2.VideoCapture(self._config.camera_index)
            if not self._capture.isOpened():
                return VisionResult(success=False, message=f"Cannot open camera {self._config.camera_index}")

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.camera_width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.camera_height)
            self._capture.set(cv2.CAP_PROP_FPS, self._config.camera_fps)

            self._initialized = True
            return VisionResult(
                success=True,
                message=f"Camera {self._config.camera_index} initialized",
                task=VisionTask.CAMERA_CAPTURE,
            )

        except Exception as exc:
            logger.error("Camera init failed: %s", exc)
            return VisionResult(success=False, message=f"Camera init failed: {exc}", error=str(exc))

    async def shutdown(self) -> None:
        """Release camera resources."""
        if self._capture:
            self._capture.release()
            self._capture = None
        self._initialized = False

    async def capture(self) -> VisionResult:
        """Capture a single frame from the camera.

        Returns:
            VisionResult with captured frame as numpy array.
        """
        if not self._initialized or not self._capture:
            return VisionResult(success=False, message="Camera not initialized")

        start = time.perf_counter()
        try:
            ret, frame = self._capture.read()
            if not ret or frame is None:
                return VisionResult(success=False, message="Failed to capture frame")

            self._frame = frame
            elapsed = (time.perf_counter() - start) * 1000

            return VisionResult(
                success=True,
                message=f"Captured {frame.shape[1]}x{frame.shape[0]} frame",
                task=VisionTask.CAMERA_CAPTURE,
                data={"frame": frame, "width": frame.shape[1], "height": frame.shape[0]},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Capture failed: {exc}", duration_ms=elapsed)

    async def capture_to_file(self, save_path: str | None = None) -> VisionResult:
        """Capture and save to file.

        Args:
            save_path: Optional save path.

        Returns:
            VisionResult with saved file path.
        """
        result = await self.capture()
        if not result.success:
            return result

        frame = result.data["frame"]
        path = save_path or f"./data/screenshots/vision/camera_{int(time.time())}.jpg"

        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(path, frame)
            result.image_path = path
            result.data = {"path": path, "width": frame.shape[1], "height": frame.shape[0]}
            result.message = f"Saved to {path}"
            return result
        except Exception as exc:
            return VisionResult(success=False, message=f"Save failed: {exc}")

    async def list_cameras(self) -> VisionResult:
        """List available cameras."""
        cameras = []
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    cameras.append({
                        "index": i,
                        "width": w,
                        "height": h,
                        "fps": fps,
                    })
                    cap.release()
            except Exception:
                continue

        return VisionResult(
            success=True,
            message=f"Found {len(cameras)} camera(s)",
            data=cameras,
        )

    async def start_stream(self, callback: Any = None, max_frames: int = 0) -> VisionResult:
        """Start a camera stream with optional callback.

        Args:
            callback: Async function called with each frame.
            max_frames: Stop after N frames (0 = unlimited).
        """
        if not self._initialized:
            return VisionResult(success=False, message="Camera not initialized")

        frame_count = 0
        try:
            while True:
                ret, frame = self._capture.read()
                if not ret:
                    break

                frame_count += 1
                if callback:
                    await callback(frame, frame_count)

                if max_frames > 0 and frame_count >= max_frames:
                    break

                await asyncio.sleep(1.0 / self._config.camera_fps)

            return VisionResult(
                success=True,
                message=f"Stream ended ({frame_count} frames)",
                data={"frames_captured": frame_count},
            )

        except asyncio.CancelledError:
            return VisionResult(success=True, message=f"Stream cancelled ({frame_count} frames)")
        except Exception as exc:
            return VisionResult(success=False, message=f"Stream failed: {exc}")

    def get_last_frame(self) -> np.ndarray | None:
        """Get the most recently captured frame."""
        return self._frame

    @staticmethod
    def save_frame(frame: np.ndarray, path: str) -> bool:
        """Save a frame to disk."""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(path, frame)
            return True
        except Exception:
            return False

    @staticmethod
    def frame_to_base64(frame: np.ndarray, format: str = ".jpg") -> str:
        """Convert a frame to base64 string."""
        import base64
        _, buffer = cv2.imencode(format, frame)
        return base64.b64encode(buffer).decode("utf-8")
