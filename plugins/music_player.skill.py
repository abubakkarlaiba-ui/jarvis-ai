"""
Skill: Music Player
===================
Manage a music queue, search local tracks, and control playback.

Requires pygame for audio playback. Install with: pip install pygame
Supports: mp3, wav, ogg, flac
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

try:
    import pygame.mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac"}
DEFAULT_MUSIC_DIRS = [
    Path.home() / "Music",
    Path.home() / "Downloads",
]


class MusicPlayerSkill(BaseSkill):
    """Play, pause, skip, and manage a local music queue."""

    metadata = SkillMetadata(
        name="music_player",
        version="1.0.0",
        description="Music queue management and playback controls",
        author="JARVIS Team",
        tags=["music", "audio", "player", "media"],
    )

    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []
        self._current_index: int = -1
        self._is_playing: bool = False
        self._scanned_tracks: list[dict[str, Any]] = []
        self._volume: float = 0.7

    async def on_initialize(self) -> None:
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
            except Exception:
                pass

    async def on_shutdown(self) -> None:
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()

    async def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "").lower()
        if not action and context.user_input.strip():
            action = context.user_input.strip().split()[0].lower()

        handlers: dict[str, Any] = {
            "add": self._add_to_queue,
            "remove": self._remove_from_queue,
            "list": self._list_queue,
            "clear": self._clear_queue,
            "play": self._play,
            "pause": self._pause,
            "stop": self._stop,
            "skip": self._skip,
            "search": self._search,
            "scan": self._scan,
            "now": self._now_playing,
            "volume": self._set_volume,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(context)

    async def _scan(self, context: SkillContext) -> SkillResult:
        dirs_param = context.parameters.get("directories", [])
        if isinstance(dirs_param, str):
            dirs_param = [d.strip() for d in dirs_param.split(",") if d.strip()]

        scan_dirs = [Path(d) for d in dirs_param] if dirs_param else DEFAULT_MUSIC_DIRS
        self._scanned_tracks.clear()

        for music_dir in scan_dirs:
            if not music_dir.is_dir():
                continue
            for file_path in music_dir.rglob("*"):
                if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    self._scanned_tracks.append({
                        "path": str(file_path),
                        "name": file_path.stem,
                        "extension": file_path.suffix.lower(),
                        "directory": str(file_path.parent),
                    })

        return SkillResult(
            success=True,
            output=f"Found {len(self._scanned_tracks)} tracks across {len(scan_dirs)} directories.",
            metadata={"count": len(self._scanned_tracks)},
        )

    async def _search(self, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", "").lower()
        if not query and context.user_input.strip():
            query = context.user_input.strip().lower()

        if not query:
            return SkillResult(success=False, error="A search query is required.")

        if not self._scanned_tracks:
            await self._scan(context)

        matches = [
            t for t in self._scanned_tracks
            if query in t["name"].lower() or fnmatch.fnmatch(t["name"].lower(), f"*{query}*")
        ]

        if not matches:
            return SkillResult(success=True, output="No matching tracks found.")

        lines = [f"[{i}] {t['name']} ({t['extension']})" for i, t in enumerate(matches)]
        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"matches": matches, "count": len(matches)},
        )

    async def _add_to_queue(self, context: SkillContext) -> SkillResult:
        track_path = context.parameters.get("path", "").strip()
        track_name = context.parameters.get("name", "").strip()

        if track_path:
            path = Path(track_path)
            if not path.is_file():
                return SkillResult(success=False, error=f"File not found: {track_path}")
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                return SkillResult(success=False, error=f"Unsupported format: {path.suffix}")
            track = {"path": str(path), "name": path.stem, "extension": path.suffix.lower()}
        elif track_name:
            if not self._scanned_tracks:
                await self._scan(context)
            found = [t for t in self._scanned_tracks if track_name.lower() in t["name"].lower()]
            if not found:
                return SkillResult(success=False, error=f"No track matching '{track_name}' found.")
            track = found[0]
        else:
            return SkillResult(success=False, error="Provide 'path' or 'name' parameter.")

        self._queue.append(track)
        return SkillResult(
            success=True,
            output=f"Added '{track['name']}' to queue (position {len(self._queue)}).",
            metadata={"queue_size": len(self._queue)},
        )

    async def _remove_from_queue(self, context: SkillContext) -> SkillResult:
        index = context.parameters.get("index", 0)
        try:
            index = int(index)
        except (ValueError, TypeError):
            return SkillResult(success=False, error="Index must be an integer.")

        if not self._queue:
            return SkillResult(success=False, error="Queue is empty.")
        if index < 0 or index >= len(self._queue):
            return SkillResult(success=False, error=f"Index {index} out of range (0-{len(self._queue) - 1}).")

        removed = self._queue.pop(index)
        if self._current_index >= len(self._queue):
            self._current_index = len(self._queue) - 1

        return SkillResult(
            success=True,
            output=f"Removed '{removed['name']}' from queue.",
            metadata={"queue_size": len(self._queue)},
        )

    async def _list_queue(self, context: SkillContext) -> SkillResult:
        if not self._queue:
            return SkillResult(success=True, output="Queue is empty.")

        lines = []
        for i, track in enumerate(self._queue):
            marker = " >> " if i == self._current_index else "    "
            lines.append(f"{marker}[{i}] {track['name']} ({track['extension']})")

        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata={"queue_size": len(self._queue), "current_index": self._current_index},
        )

    async def _clear_queue(self, context: SkillContext) -> SkillResult:
        count = len(self._queue)
        self._queue.clear()
        self._current_index = -1
        self._is_playing = False
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.stop()
        return SkillResult(success=True, output=f"Cleared {count} tracks from queue.")

    async def _play(self, context: SkillContext) -> SkillResult:
        if not self._queue:
            return SkillResult(success=False, error="Queue is empty. Add tracks first.")

        index = context.parameters.get("index", None)
        if index is not None:
            try:
                self._current_index = int(index)
            except (ValueError, TypeError):
                return SkillResult(success=False, error="Index must be an integer.")
        elif self._current_index < 0:
            self._current_index = 0

        if self._current_index < 0 or self._current_index >= len(self._queue):
            return SkillResult(success=False, error="Invalid queue position.")

        track = self._queue[self._current_index]

        if not PYGAME_AVAILABLE:
            return SkillResult(
                success=False,
                error="pygame is not installed. Install with: pip install pygame",
            )

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as exc:
                return SkillResult(success=False, error=f"Failed to init audio: {exc}")

        try:
            pygame.mixer.music.load(track["path"])
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play()
            self._is_playing = True
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to play '{track['name']}': {exc}")

        return SkillResult(
            success=True,
            output=f"Now playing: {track['name']}",
            metadata={"track": track, "index": self._current_index},
        )

    async def _pause(self, context: SkillContext) -> SkillResult:
        if not PYGAME_AVAILABLE or not pygame.mixer.get_init():
            return SkillResult(success=False, error="Audio system not available.")
        if not self._is_playing:
            return SkillResult(success=False, error="Nothing is currently playing.")

        pygame.mixer.music.pause()
        self._is_playing = False
        return SkillResult(success=True, output="Playback paused.")

    async def _stop(self, context: SkillContext) -> SkillResult:
        if not PYGAME_AVAILABLE or not pygame.mixer.get_init():
            return SkillResult(success=False, error="Audio system not available.")

        pygame.mixer.music.stop()
        self._is_playing = False
        return SkillResult(success=True, output="Playback stopped.")

    async def _skip(self, context: SkillContext) -> SkillResult:
        if not self._queue:
            return SkillResult(success=False, error="Queue is empty.")

        self._current_index += 1
        if self._current_index >= len(self._queue):
            self._current_index = 0

        if self._is_playing:
            return await self._play(context)

        track = self._queue[self._current_index]
        return SkillResult(
            success=True,
            output=f"Skipped to: {track['name']} (position {self._current_index})",
            metadata={"index": self._current_index},
        )

    async def _now_playing(self, context: SkillContext) -> SkillResult:
        if not self._is_playing or self._current_index < 0:
            return SkillResult(success=True, output="Nothing is currently playing.")

        track = self._queue[self._current_index]
        return SkillResult(
            success=True,
            output=f"Now playing: {track['name']} (track {self._current_index + 1}/{len(self._queue)})",
            metadata={"track": track, "index": self._current_index, "playing": True},
        )

    async def _set_volume(self, context: SkillContext) -> SkillResult:
        level = context.parameters.get("level", 0.7)
        try:
            level = float(level)
        except (ValueError, TypeError):
            return SkillResult(success=False, error="Volume must be a number between 0.0 and 1.0.")

        level = max(0.0, min(1.0, level))
        self._volume = level

        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.music.set_volume(level)

        return SkillResult(
            success=True,
            output=f"Volume set to {level:.0%}",
            metadata={"volume": level},
        )
