"""
Real-time screen monitor for JARVIS vision system.
====================================================
Continuously monitor the screen for changes, errors, and events.

Supports:
    - Continuous screen monitoring
    - Change detection
    - Error detection
    - Activity logging
    - Event callbacks

Usage:
    monitor = ScreenMonitor(config)
    await monitor.start(callback=my_callback)
    await monitor.stop()
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from typing import Any, Callable, Awaitable

import cv2
import numpy as np

from jarvis.core.vision.base import VisionConfig, VisionResult, VisionTask, ScreenChange

logger = logging.getLogger(__name__)


class ScreenMonitor:
    """Real-time screen monitoring with change detection.

    Example:
        config = VisionConfig(monitor_interval=2.0)
        monitor = ScreenMonitor(config)

        async def on_change(change):
            print(f"Screen changed: {change.description}")

        await monitor.start(callback=on_change)
    """

    def __init__(self, config: VisionConfig):
        self._config = config
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_frame: np.ndarray | None = None
        self._last_hash: str = ""
        self._changes: deque[ScreenChange] = deque(maxlen=100)
        self._callback: Callable[[ScreenChange], Awaitable[None]] | None = None
        self._frame_callback: Callable[[np.ndarray, int], Awaitable[None]] | None = None

    async def start(
        self,
        callback: Callable[[ScreenChange], Awaitable[None]] | None = None,
        frame_callback: Callable[[np.ndarray, int], Awaitable[None]] | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> VisionResult:
        """Start monitoring the screen.

        Args:
            callback: Called when a change is detected.
            frame_callback: Called with each captured frame.
            region: Optional (x, y, w, h) region to monitor.

        Returns:
            VisionResult with start status.
        """
        if self._running:
            return VisionResult(success=False, message="Monitor already running")

        self._running = True
        self._callback = callback
        self._frame_callback = frame_callback

        self._task = asyncio.create_task(self._monitor_loop(region))

        return VisionResult(
            success=True,
            message=f"Screen monitor started (interval: {self._config.monitor_interval}s)",
            task=VisionTask.SCREEN_MONITOR,
        )

    async def stop(self) -> VisionResult:
        """Stop monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        return VisionResult(
            success=True,
            message=f"Monitor stopped ({len(self._changes)} changes detected)",
            data={"changes_count": len(self._changes)},
        )

    async def _monitor_loop(self, region: tuple[int, int, int, int] | None = None) -> None:
        """Main monitoring loop."""
        try:
            while self._running:
                frame = await self._capture_screen(region)
                if frame is None:
                    await asyncio.sleep(1)
                    continue

                if self._frame_callback:
                    await self._frame_callback(frame, int(time.time()))

                change = self._detect_change(frame)

                if change and self._callback:
                    await self._callback(change)

                self._last_frame = frame
                self._last_hash = hashlib.md5(frame.tobytes()).hexdigest()

                await asyncio.sleep(self._config.monitor_interval)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Monitor loop error: %s", exc)

    async def _capture_screen(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray | None:
        """Capture screen frame."""
        try:
            import mss
            with mss.mss() as sct:
                if region:
                    monitor = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
                else:
                    monitor = sct.monitors[1]

                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                return frame

        except Exception as exc:
            logger.debug("Screen capture failed: %s", exc)
            return None

    def _detect_change(self, frame: np.ndarray) -> ScreenChange | None:
        """Detect changes between current and previous frame."""
        if self._last_frame is None:
            return None

        try:
            if frame.shape != self._last_frame.shape:
                self._last_frame = cv2.resize(self._last_frame, (frame.shape[1], frame.shape[0]))

            gray1 = cv2.cvtColor(self._last_frame, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            diff = cv2.absdiff(gray1, gray2)
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

            change_ratio = np.count_nonzero(thresh) / thresh.size

            if change_ratio < self._config.monitor_change_threshold:
                return None

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_region = (0, 0, frame.shape[1], frame.shape[0])

            for cnt in contours:
                if cv2.contourArea(cnt) > 500:
                    x, y, w, h = cv2.boundingRect(cnt)
                    max_region = (x, y, w, h)
                    break

            change = ScreenChange(
                timestamp=time.time(),
                region=max_region,
                change_type="content",
                old_hash=self._last_hash,
                new_hash=hashlib.md5(frame.tobytes()).hexdigest(),
                description=f"Screen changed ({change_ratio:.1%} pixels)",
            )

            self._changes.append(change)
            return change

        except Exception as exc:
            logger.debug("Change detection error: %s", exc)
            return None

    async def check_once(self, region: tuple[int, int, int, int] | None = None) -> VisionResult:
        """Perform a single screen check."""
        frame = await self._capture_screen(region)
        if frame is None:
            return VisionResult(success=False, message="Screen capture failed")

        change = self._detect_change(frame)
        self._last_frame = frame
        self._last_hash = hashlib.md5(frame.tobytes()).hexdigest()

        return VisionResult(
            success=True,
            message="Change detected" if change else "No change",
            task=VisionTask.SCREEN_MONITOR,
            data={
                "changed": change is not None,
                "change": change.to_dict() if change else None,
                "total_changes": len(self._changes),
            },
        )

    def get_changes(self, limit: int = 20) -> list[dict]:
        """Get recent detected changes."""
        return [c.to_dict() for c in list(self._changes)[-limit:]]

    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "total_changes": len(self._changes),
            "monitor_interval": self._config.monitor_interval,
            "change_threshold": self._config.monitor_change_threshold,
        }
