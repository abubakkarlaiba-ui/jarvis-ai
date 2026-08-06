"""
Skill: Email
=============
Send, read, and search emails via IMAP/SMTP.

Requires environment variables:
    EMAIL_IMAP_HOST   — IMAP server hostname (e.g. imap.gmail.com)
    EMAIL_SMTP_HOST   — SMTP server hostname (e.g. smtp.gmail.com)
    EMAIL_ADDRESS     — Full email address
    EMAIL_PASSWORD    — App password or account password
"""

from __future__ import annotations

import asyncio
import email
import email.mime.text
import email.utils
import os
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult


def _env(name: str) -> str | None:
    return os.getenv(name)


def _has_config() -> bool:
    return all(
        _env(v) is not None
        for v in ("EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST", "EMAIL_ADDRESS", "EMAIL_PASSWORD")
    )


def _missing_config() -> list[str]:
    return [v for v in ("EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST", "EMAIL_ADDRESS", "EMAIL_PASSWORD") if _env(v) is None]


def _decode_header_value(raw: Any) -> str:
    if raw is None:
        return ""
    parts = decode_header(raw)
    decoded: list[str] = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return "".join(decoded)


def _format_message(msg: email.message.Message, index: int) -> str:
    subject = _decode_header_value(msg.get("Subject"))
    sender = msg.get("From", "")
    date = msg.get("Date", "")
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and part.get("Content-Disposition") != "attachment":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    snippet = body.strip().replace("\n", " ")[:120]
    return f"{index}. From: {sender}\n   Subject: {subject}\n   Date: {date}\n   Preview: {snippet}"


async def _imap_search(
    folder: str,
    criteria: str,
    limit: int,
) -> tuple[str, list[str]]:
    """Run an IMAP search in a thread to avoid blocking the event loop."""
    import imaplib

    host = _env("EMAIL_IMAP_HOST") or ""
    addr = _env("EMAIL_ADDRESS") or ""
    password = _env("EMAIL_PASSWORD") or ""

    def _work() -> list[str]:
        imap = imaplib.IMAP4_SSL(host, timeout=15)
        imap.login(addr, password)
        imap.select(folder, readonly=True)
        _, msg_nums = imap.search(None, criteria)
        ids = msg_nums[0].split()
        # Return newest first, capped to limit
        ids = ids[-limit:][::-1]
        raw_messages: list[str] = []
        for mid in ids:
            _, data = imap.fetch(mid, "(RFC822)")
            raw_messages.append(data[0][1])
        imap.logout()
        return raw_messages

    loop = asyncio.get_running_loop()
    raw_list = await loop.run_in_executor(None, _work)
    return host, raw_list


async def _smtp_send(to: str, subject: str, body: str) -> None:
    """Send an email via SMTP in a thread."""
    import smtplib

    host = _env("EMAIL_SMTP_HOST") or ""
    addr = _env("EMAIL_ADDRESS") or ""
    password = _env("EMAIL_PASSWORD") or ""

    def _work() -> None:
        msg = email.mime.text.MIMEText(body, "plain", "utf-8")
        msg["From"] = addr
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)

        with smtplib.SMTP_SSL(host, timeout=15) as server:
            server.login(addr, password)
            server.sendmail(addr, to, msg.as_string())

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _work)


def _parse_messages(raw_list: list[str], limit: int) -> list[email.message.Message]:
    messages: list[email.message.Message] = []
    for raw in raw_list[:limit]:
        try:
            messages.append(email.message_from_bytes(raw))
        except Exception:
            continue
    return messages


class EmailSkill(BaseSkill):
    """Send, read, and search emails via IMAP/SMTP.

    Supported actions (via context.parameters["action"]):
        read    — Fetch unread inbox messages (default)
        send    — Send an email (requires to, subject, body)
        search  — Search emails (requires query)
    """

    metadata = SkillMetadata(
        name="email",
        version="1.0.0",
        description="Send, read, and search emails via IMAP/SMTP",
        author="JARVIS Team",
        tags=["email", "messaging", "communication"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        if not _has_config():
            missing = ", ".join(_missing_config())
            return SkillResult(
                success=False,
                error=f"Email not configured. Missing env vars: {missing}",
            )

        action = context.parameters.get("action", "read").lower().strip()

        if action == "send":
            return await self._send_email(context)
        if action == "search":
            return await self._search_emails(context)
        return await self._read_inbox(context)

    # ── Read inbox ──────────────────────────────────────────────

    async def _read_inbox(self, context: SkillContext) -> SkillResult:
        limit = int(context.parameters.get("limit", 5))
        folder = context.parameters.get("folder", "INBOX")

        try:
            _, raw_list = await _imap_search(folder, "UNSEEN", limit)
        except Exception as exc:
            return SkillResult(success=False, error=f"IMAP error: {exc}")

        if not raw_list:
            return SkillResult(
                success=True,
                output="No unread messages in your inbox.",
                metadata={"folder": folder, "count": 0},
            )

        messages = _parse_messages(raw_list, limit)
        lines = [_format_message(msg, i + 1) for i, msg in enumerate(messages)]
        header = f"Unread messages in {folder} ({len(messages)}):\n\n"

        return SkillResult(
            success=True,
            output=header + "\n\n".join(lines),
            metadata={"folder": folder, "count": len(messages)},
        )

    # ── Send email ──────────────────────────────────────────────

    async def _send_email(self, context: SkillContext) -> SkillResult:
        to = context.parameters.get("to", "").strip()
        subject = context.parameters.get("subject", "").strip()
        body = context.parameters.get("body", "").strip()

        if not to:
            return SkillResult(success=False, error="Recipient address is required (parameter 'to').")
        if not subject and not body:
            return SkillResult(success=False, error="Subject or body must be provided.")

        try:
            await _smtp_send(to, subject or "(no subject)", body or "")
        except Exception as exc:
            return SkillResult(success=False, error=f"SMTP error: {exc}")

        return SkillResult(
            success=True,
            output=f"Email sent to {to}.",
            metadata={"to": to, "subject": subject},
        )

    # ── Search ──────────────────────────────────────────────────

    async def _search_emails(self, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", "").strip()
        if not query:
            return SkillResult(success=False, error="Search query is required (parameter 'query').")

        limit = int(context.parameters.get("limit", 5))
        folder = context.parameters.get("folder", "INBOX")

        criteria = f'(OR SUBJECT "{query}" FROM "{query}")'
        try:
            _, raw_list = await _imap_search(folder, criteria, limit)
        except Exception as exc:
            return SkillResult(success=False, error=f"IMAP search error: {exc}")

        if not raw_list:
            return SkillResult(
                success=True,
                output=f"No messages matching '{query}' in {folder}.",
                metadata={"query": query, "folder": folder, "count": 0},
            )

        messages = _parse_messages(raw_list, limit)
        lines = [_format_message(msg, i + 1) for i, msg in enumerate(messages)]
        header = f"Results for '{query}' in {folder} ({len(messages)}):\n\n"

        return SkillResult(
            success=True,
            output=header + "\n\n".join(lines),
            metadata={"query": query, "folder": folder, "count": len(messages)},
        )
