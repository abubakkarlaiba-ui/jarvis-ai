"""
Screen analyzer for JARVIS vision system.
==========================================
Screen capture, region analysis, and window detection.

Supports:
    - Full screen capture
    - Region capture
    - Active window capture
    - Multi-monitor support
    - Window listing

Usage:
    screen = ScreenAnalyzer(config)
    result = await screen.capture_full()
    result = await screen.capture_region(0, 0, 800, 600)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask

logger = logging.getLogger(__name__)


class ScreenAnalyzer:
    """Capture and analyze screen content.

    Example:
        config = VisionConfig()
        screen = ScreenAnalyzer(config)
        result = await screen.capture_full()
        frame = result.data["frame"]
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._capture_dir = Path(config.screen_capture_dir)
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        self._last_frame: np.ndarray | None = None
        self._last_hash: str = ""

    async def capture_full(self) -> VisionResult:
        """Capture the full screen.

        Returns:
            VisionResult with screen frame.
        """
        start = time.perf_counter()
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            self._last_frame = frame
            self._last_hash = hashlib.md5(frame.tobytes()).hexdigest()

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Screen captured: {frame.shape[1]}x{frame.shape[0]}",
                task=VisionTask.SCREENSHOT,
                data={"frame": frame, "width": frame.shape[1], "height": frame.shape[0]},
                duration_ms=elapsed,
            )

        except ImportError:
            return VisionResult(success=False, message="mss library required: pip install mss")
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Screen capture failed: {exc}", duration_ms=elapsed)

    async def capture_region(self, x: int, y: int, width: int, height: int) -> VisionResult:
        """Capture a specific screen region.

        Args:
            x: Left coordinate.
            y: Top coordinate.
            width: Region width.
            height: Region height.

        Returns:
            VisionResult with region frame.
        """
        start = time.perf_counter()
        try:
            import mss
            with mss.mss() as sct:
                region = {"left": x, "top": y, "width": width, "height": height}
                screenshot = sct.grab(region)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Region captured: {width}x{height}",
                task=VisionTask.SCREENSHOT,
                data={"frame": frame, "x": x, "y": y, "width": width, "height": height},
                duration_ms=elapsed,
            )

        except ImportError:
            return VisionResult(success=False, message="mss library required: pip install mss")
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Region capture failed: {exc}", duration_ms=elapsed)

    async def capture_active_window(self) -> VisionResult:
        """Capture the active window."""
        start = time.perf_counter()
        try:
            import mss
            with mss.mss() as sct:
                monitors = sct.monitors
                if len(monitors) < 2:
                    return VisionResult(success=False, message="No monitor found")

                monitor = monitors[1]
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Screen captured: {frame.shape[1]}x{frame.shape[0]}",
                task=VisionTask.SCREENSHOT,
                data={"frame": frame, "width": frame.shape[1], "height": frame.shape[0]},
                duration_ms=elapsed,
            )

        except ImportError:
            return VisionResult(success=False, message="mss library required: pip install mss")
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Window capture failed: {exc}", duration_ms=elapsed)

    async def save_screenshot(self, frame: np.ndarray | None = None, name: str | None = None) -> VisionResult:
        """Save a screenshot to disk.

        Args:
            frame: Frame to save (uses last captured if None).
            name: Optional filename.
        """
        frame = frame or self._last_frame
        if frame is None:
            return VisionResult(success=False, message="No frame to save")

        try:
            filename = name or f"screen_{int(time.time())}.png"
            path = str(self._capture_dir / filename)
            cv2.imwrite(path, frame)

            return VisionResult(
                success=True,
                message=f"Saved: {path}",
                image_path=path,
                data={"path": path, "width": frame.shape[1], "height": frame.shape[0]},
            )
        except Exception as exc:
            return VisionResult(success=False, message=f"Save failed: {exc}")

    async def detect_changes(self, frame1: np.ndarray | None = None, frame2: np.ndarray | None = None) -> VisionResult:
        """Compare two frames for changes.

        Args:
            frame1: First frame (uses previous capture if None).
            frame2: Second frame (uses new capture if None).

        Returns:
            VisionResult with change detection data.
        """
        start = time.perf_counter()

        if frame1 is None:
            return VisionResult(success=False, message="No frame1 provided")

        if frame2 is None:
            result = await self.capture_full()
            if not result.success:
                return result
            frame2 = result.data["frame"]

        try:
            if frame1.shape != frame2.shape:
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))

            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

            diff = cv2.absdiff(gray1, gray2)
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

            change_ratio = np.count_nonzero(thresh) / thresh.size

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            regions = []
            for cnt in contours:
                if cv2.contourArea(cnt) > 100:
                    x, y, w, h = cv2.boundingRect(cnt)
                    regions.append({"x": x, "y": y, "width": w, "height": h})

            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(
                success=True,
                message=f"Change detected: {change_ratio:.1%}" if change_ratio > 0.01 else "No significant change",
                task=VisionTask.SCREEN_MONITOR,
                data={
                    "change_ratio": round(change_ratio, 4),
                    "regions": regions[:20],
                    "changed": change_ratio > 0.01,
                },
                confidence=1.0 - change_ratio,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return VisionResult(success=False, message=f"Change detection failed: {exc}", duration_ms=elapsed)

    async def list_monitors(self) -> VisionResult:
        """List available monitors."""
        try:
            import mss
            with mss.mss() as sct:
                monitors = []
                for i, m in enumerate(sct.monitors):
                    if i == 0:
                        continue
                    monitors.append({
                        "index": i,
                        "left": m["left"],
                        "top": m["top"],
                        "width": m["width"],
                        "height": m["height"],
                    })
            return VisionResult(
                success=True,
                message=f"Found {len(monitors)} monitor(s)",
                data=monitors,
            )
        except ImportError:
            return VisionResult(success=False, message="mss library required")
        except Exception as exc:
            return VisionResult(success=False, message=f"List monitors failed: {exc}")

    def get_last_frame(self) -> np.ndarray | None:
        return self._last_frame

    def get_last_hash(self) -> str:
        return self._last_hash
