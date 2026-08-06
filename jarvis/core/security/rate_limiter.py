"""
Security module — Token bucket rate limiting for API endpoints and actions.
"""

from __future__ import annotations

import time
import threading
from typing import Any

from jarvis.core.security.base import AuditAction


class RateLimiter:
    """
    Token bucket rate limiter with per-key limits and IP blocking.

    Tokens refill at a constant rate (limit / window per second), capped at the
    bucket maximum (limit).  Keys can carry custom overrides; missing keys use
    the default limit.  IPs that exceed a violation threshold are temporarily
    blocked.
    """

    def __init__(self, default_limit: int = 60, default_window: int = 60) -> None:
        self._default_limit = default_limit
        self._default_window = default_window
        self._buckets: dict[str, dict[str, Any]] = {}
        self._custom_limits: dict[str, tuple[int, int]] = {}
        self._blocked_ips: dict[str, float] = {}
        self._ip_violations: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._total_requests = 0
        self._total_blocked = 0
        self._key_stats: dict[str, dict[str, int]] = {}

    def _get_bucket(self, key: str) -> dict[str, Any]:
        """Get or create a token bucket for *key*."""
        now = time.time()
        with self._lock:
            if key in self._buckets:
                bucket = self._buckets[key]
                self._refill(bucket, now)
                return bucket
            limit, window = self._custom_limits.get(key, (self._default_limit, self._default_window))
            bucket = {
                "tokens": float(limit),
                "max_tokens": float(limit),
                "refill_rate": limit / window,
                "last_refill": now,
            }
            self._buckets[key] = bucket
            return bucket

    def _refill(self, bucket: dict[str, Any], now: float) -> None:
        """Add tokens based on elapsed time."""
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(bucket["max_tokens"], bucket["tokens"] + elapsed * bucket["refill_rate"])
        bucket["last_refill"] = now

    def check(self, key: str, cost: int = 1) -> tuple[bool, dict[str, Any]]:
        """
        Check if a request of *cost* tokens is allowed without consuming.

        Returns ``(allowed, info)`` where *info* contains ``limit``,
        ``remaining``, and ``reset_at`` (seconds until the bucket is full).
        """
        bucket = self._get_bucket(key)
        with self._lock:
            allowed = bucket["tokens"] >= cost
            remaining = int(bucket["tokens"]) if allowed else 0
            reset_at = (bucket["max_tokens"] - bucket["tokens"]) / bucket["refill_rate"] if bucket["refill_rate"] else 0
            return allowed, {
                "limit": int(bucket["max_tokens"]),
                "remaining": remaining,
                "reset_at": round(reset_at, 2),
            }

    def consume(self, key: str, cost: int = 1) -> bool:
        """Consume *cost* tokens; return ``True`` if the request is allowed."""
        bucket = self._get_bucket(key)
        with self._lock:
            self._total_requests += 1
            self._key_stats.setdefault(key, {"total": 0, "blocked": 0})
            self._key_stats[key]["total"] += 1
            if bucket["tokens"] >= cost:
                bucket["tokens"] -= cost
                return True
            self._total_blocked += 1
            self._key_stats[key]["blocked"] += 1
            self._record_violation(key)
            return False

    def get_remaining(self, key: str) -> int:
        """Return the current number of available tokens for *key*."""
        bucket = self._get_bucket(key)
        with self._lock:
            return int(bucket["tokens"])

    def get_reset_time(self, key: str) -> float:
        """Seconds until the bucket is refilled to maximum."""
        bucket = self._get_bucket(key)
        with self._lock:
            return round((bucket["max_tokens"] - bucket["tokens"]) / bucket["refill_rate"], 2) if bucket["refill_rate"] else 0.0

    def set_limit(self, key: str, limit: int, window: int = 60) -> None:
        """Set a custom limit for a specific key."""
        with self._lock:
            self._custom_limits[key] = (limit, window)
            if key in self._buckets:
                del self._buckets[key]

    def remove_limit(self, key: str) -> None:
        """Remove custom limit for *key*, falling back to defaults."""
        with self._lock:
            self._custom_limits.pop(key, None)
            if key in self._buckets:
                del self._buckets[key]

    def cleanup(self) -> int:
        """Remove expired or empty buckets; return the count removed."""
        now = time.time()
        removed = 0
        with self._lock:
            expired = [
                k for k, b in self._buckets.items()
                if b["tokens"] >= b["max_tokens"] and (now - b["last_refill"]) > b["max_tokens"] / b["refill_rate"] * 2
            ]
            for k in expired:
                del self._buckets[k]
                removed += 1
            expired_blocked = [ip for ip, until in self._blocked_ips.items() if now > until]
            for ip in expired_blocked:
                del self._blocked_ips[ip]
                self._ip_violations.pop(ip, None)
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "total_blocked": self._total_blocked,
                "active_buckets": len(self._buckets),
                "blocked_ips": len(self._blocked_ips),
                "by_key": dict(self._key_stats),
            }

    def is_ip_blocked(self, ip: str) -> bool:
        """Check whether *ip* is currently blocked."""
        now = time.time()
        with self._lock:
            until = self._blocked_ips.get(ip)
            if until and now < until:
                return True
            if until and now >= until:
                del self._blocked_ips[ip]
                self._ip_violations.pop(ip, None)
            return False

    def block_ip(self, ip: str, duration: int = 300) -> None:
        """Block *ip* for *duration* seconds."""
        with self._lock:
            self._blocked_ips[ip] = time.time() + duration

    def reset(self, key: str) -> None:
        """Reset a bucket to full capacity."""
        with self._lock:
            self._buckets.pop(key, None)

    async def middleware_handler(self, request: Any) -> None:
        """
        FastAPI-compatible rate check middleware helper.

        Call ``await rate_limiter.middleware_handler(request)`` inside a
        ``before_request``-style hook.  Raises ``HTTPException(429)`` when
        the limit is exceeded.
        """
        client_ip = getattr(request, "client", None)
        ip = client_ip.host if client_ip else "unknown"
        if self.is_ip_blocked(ip):
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="IP temporarily blocked")

        key = f"{ip}:{getattr(request, 'url', {}).path}"
        allowed, info = self.check(key)
        if not allowed:
            self._record_violation(ip)
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    def _record_violation(self, ip: str) -> None:
        """Track violations and auto-block IPs that exceed thresholds."""
        now = time.time()
        with self._lock:
            violations = self._ip_violations.setdefault(ip, [])
            violations.append(now)
            violations[:] = [t for t in violations if now - t < 60]
            if len(violations) >= 20:
                self._blocked_ips[ip] = now + 300
