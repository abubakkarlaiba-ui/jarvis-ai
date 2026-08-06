"""
Skill: YouTube Assistant
========================
Extract video info, download audio, get transcripts, and search YouTube.

Requires yt-dlp. Install with: pip install yt-dlp
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

try:
    import yt_dlp

    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False


class YouTubeAssistantSkill(BaseSkill):
    metadata = SkillMetadata(
        name="youtube_assistant",
        version="1.0.0",
        description="YouTube video info extraction, audio download, transcripts, and search",
        author="JARVIS Team",
        tags=["youtube", "video", "media", "transcript"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        if not YTDLP_AVAILABLE:
            return SkillResult(
                success=False,
                error="yt-dlp is not installed. Install with: pip install yt-dlp",
            )

        action = context.parameters.get("action", "").lower()
        if not action and context.user_input.strip():
            action = context.user_input.strip().split()[0].lower()

        handlers: dict[str, Any] = {
            "info": self._get_info,
            "download": self._download_audio,
            "transcript": self._get_transcript,
            "search": self._search_videos,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(context)

    async def _run_ytdlp(self, url: str, extra_opts: dict[str, Any] | None = None) -> dict[str, Any] | str:
        loop = asyncio.get_running_loop()

        def _extract() -> dict[str, Any]:
            opts: dict[str, Any] = {"quiet": True, "no_warnings": True}
            if extra_opts:
                opts.update(extra_opts)
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        return await loop.run_in_executor(None, _extract)

    async def _run_download(self, url: str, opts: dict[str, Any]) -> str:
        loop = asyncio.get_running_loop()

        def _download() -> str:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    return ""
                return ydl.prepare_filename(info)

        return await loop.run_in_executor(None, _download)

    def _extract_video_meta(self, info: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": info.get("title", ""),
            "description": (info.get("description", "") or "")[:500],
            "duration": info.get("duration", 0),
            "duration_string": info.get("duration_string", ""),
            "view_count": info.get("view_count", 0),
            "channel": info.get("channel", "") or info.get("uploader", ""),
            "upload_date": info.get("upload_date", ""),
            "url": info.get("webpage_url", ""),
            "thumbnail": info.get("thumbnail", ""),
            "tags": info.get("tags", []),
        }

    async def _get_info(self, context: SkillContext) -> SkillResult:
        url = context.parameters.get("url", "").strip()
        if not url:
            return SkillResult(success=False, error="A YouTube URL is required.")

        try:
            info = await self._run_ytdlp(url)
            meta = self._extract_video_meta(info)
            output = (
                f"Title: {meta['title']}\n"
                f"Channel: {meta['channel']}\n"
                f"Duration: {meta['duration_string']} ({meta['duration']}s)\n"
                f"Views: {meta['view_count']:,}\n"
                f"Upload Date: {meta['upload_date']}\n"
                f"URL: {meta['url']}\n"
                f"Description:\n{meta['description'][:300]}"
            )
            return SkillResult(success=True, output=output, metadata=meta)
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to extract video info: {exc}")

    async def _download_audio(self, context: SkillContext) -> SkillResult:
        url = context.parameters.get("url", "").strip()
        output_dir = context.parameters.get("output_dir", "./data/youtube_audio")
        if not url:
            return SkillResult(success=False, error="A YouTube URL is required.")

        opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            filename = await self._run_download(url, opts)
            return SkillResult(
                success=True,
                output=f"Audio downloaded: {filename}",
                metadata={"file": filename},
            )
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to download audio: {exc}")

    async def _get_transcript(self, context: SkillContext) -> SkillResult:
        url = context.parameters.get("url", "").strip()
        lang = context.parameters.get("lang", "en")
        if not url:
            return SkillResult(success=False, error="A YouTube URL is required.")

        loop = asyncio.get_running_loop()

        def _extract_subs() -> tuple[dict[str, Any], dict[str, Any]]:
            opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [lang],
                "subtitlesformat": "json3",
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info or {}, {}

        try:
            info, _ = await loop.run_in_executor(None, _extract_subs)
            subs = info.get("subtitles", {})
            auto_subs = info.get("automatic_captions", {})

            available = list(subs.keys())
            auto_available = list(auto_subs.keys())

            sub_key = lang if lang in subs else lang if lang in auto_subs else None
            if sub_key is None and subs:
                sub_key = next(iter(subs))
            elif sub_key is None and auto_subs:
                sub_key = next(iter(auto_subs))

            if sub_key is None:
                return SkillResult(
                    success=True,
                    output=f"No subtitles available. Available manual: {available}, auto: {auto_available}",
                    metadata={"manual": available, "auto": auto_available},
                )

            sub_data = subs.get(sub_key) or auto_subs.get(sub_key, [])
            if not sub_data:
                return SkillResult(success=True, output=f"Subtitle entry found for '{sub_key}' but no data.")

            text_parts = []
            for entry in sub_data:
                text = entry.get("data", {}).get("content", entry.get("content", ""))
                if text:
                    text_parts.append(text.strip())

            transcript = " ".join(text_parts) if text_parts else "Could not parse transcript text."
            return SkillResult(
                success=True,
                output=transcript[:2000],
                metadata={"language": sub_key, "chars": len(transcript)},
            )
        except Exception as exc:
            return SkillResult(success=False, error=f"Failed to get transcript: {exc}")

    async def _search_videos(self, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", "").strip()
        max_results = int(context.parameters.get("max_results", 5))
        if not query:
            return SkillResult(success=False, error="A search query is required.")

        loop = asyncio.get_running_loop()

        def _search() -> list[dict[str, str]]:
            opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "default_search": "ytsearch",
                "skip_download": True,
            }
            search_url = f"ytsearch{max_results}:{query}"
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                if info is None:
                    return []
                entries = info.get("entries", [])
                results = []
                for entry in entries:
                    if entry:
                        results.append({
                            "title": entry.get("title", ""),
                            "url": entry.get("webpage_url", ""),
                            "channel": entry.get("channel", entry.get("uploader", "")),
                            "duration": entry.get("duration_string", ""),
                            "views": str(entry.get("view_count", 0)),
                        })
                return results

        try:
            results = await loop.run_in_executor(None, _search)
            if not results:
                return SkillResult(success=True, output="No results found.")

            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"[{i}] {r['title']}")
                lines.append(f"    Channel: {r['channel']} | Duration: {r['duration']} | Views: {r['views']}")
                lines.append(f"    URL: {r['url']}")
                lines.append("")

            return SkillResult(
                success=True,
                output="\n".join(lines),
                metadata={"results": results, "count": len(results)},
            )
        except Exception as exc:
            return SkillResult(success=False, error=f"Search failed: {exc}")
