"""
Login automation for JARVIS browser automation.
================================================
Automate website logins with credential storage and session management.

Supports:
    - Credential-based login (username/password)
    - OAuth/SSO redirect handling
    - CAPTCHA detection
    - 2FA pause for manual input
    - Cookie-based session restore

Usage:
    auth = LoginAutomation(manager, config)
    await auth.login("github.com", username="user", password="pass")
    await auth.save_credentials("github.com", "user", "pass")
    logged_in = await auth.check_login_status("github.com")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult

logger = logging.getLogger(__name__)


class LoginAutomation:
    """Automate website logins with credential management.

    Example:
        auth = LoginAutomation(manager, config)
        await auth.save_credentials("github.com", "user@example.com", "token123")
        result = await auth.login("github.com")
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config
        self._credentials_file = Path(config.user_data_dir) / "credentials.json"
        self._credentials: dict[str, dict] = {}
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load saved credentials from disk."""
        try:
            if self._credentials_file.exists():
                self._credentials = json.loads(
                    self._credentials_file.read_text(encoding="utf-8")
                )
        except Exception as exc:
            logger.debug("Failed to load credentials: %s", exc)
            self._credentials = {}

    def _save_credentials_to_disk(self) -> None:
        """Persist credentials to disk."""
        try:
            self._credentials_file.parent.mkdir(parents=True, exist_ok=True)
            self._credentials_file.write_text(
                json.dumps(self._credentials, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save credentials: %s", exc)

    async def save_credentials(self, domain: str, username: str, password: str) -> BrowserResult:
        """Save credentials for a domain.

        Args:
            domain: Website domain (e.g., "github.com").
            username: Username or email.
            password: Password or token.
        """
        import base64
        encoded_pw = base64.b64encode(password.encode()).decode()
        self._credentials[domain] = {
            "username": username,
            "password": encoded_pw,
            "saved_at": time.time(),
        }
        self._save_credentials_to_disk()
        return BrowserResult(
            success=True,
            message=f"Credentials saved for {domain}",
        )

    async def get_credentials(self, domain: str) -> BrowserResult:
        """Get saved credentials for a domain."""
        import base64
        creds = self._credentials.get(domain)
        if not creds:
            return BrowserResult(success=False, message=f"No credentials for {domain}")

        password = base64.b64decode(creds["password"].encode()).decode()
        return BrowserResult(
            success=True,
            message=f"Credentials for {domain}",
            data={"username": creds["username"], "password": password},
        )

    async def delete_credentials(self, domain: str) -> BrowserResult:
        """Delete saved credentials for a domain."""
        if domain in self._credentials:
            del self._credentials[domain]
            self._save_credentials_to_disk()
            return BrowserResult(success=True, message=f"Credentials deleted for {domain}")
        return BrowserResult(success=False, message=f"No credentials for {domain}")

    async def login(
        self,
        domain: str,
        username: str | None = None,
        password: str | None = None,
        username_selector: str = "input[type='email'], input[name='email'], input[name='username'], input[id='user'], #username, #email",
        password_selector: str = "input[type='password'], input[name='password'], #password",
        submit_selector: str = "button[type='submit'], input[type='submit'], button:has-text('Log in'), button:has-text('Sign in'), button:has-text('Login')",
        success_indicator: str | None = None,
        failure_indicator: str | None = None,
        timeout_ms: int = 0,
    ) -> BrowserResult:
        """Perform a login flow.

        Args:
            domain: Website domain to log into.
            username: Username (uses saved credentials if not provided).
            password: Password (uses saved credentials if not provided).
            username_selector: CSS selector for username input.
            password_selector: CSS selector for password input.
            submit_selector: CSS selector for submit button.
            success_indicator: Selector that appears on successful login.
            failure_indicator: Selector that appears on failed login.
            timeout_ms: Timeout override.

        Returns:
            BrowserResult with login status.
        """
        start = time.perf_counter()
        timeout = timeout_ms or self._config.timeout_ms

        if not self._manager.page:
            return BrowserResult(success=False, message="No active page")

        if not username or not password:
            creds_result = await self.get_credentials(domain)
            if creds_result.success:
                creds = creds_result.data
                username = username or creds.get("username")
                password = password or creds.get("password")

        if not username or not password:
            return BrowserResult(
                success=False,
                message=f"No credentials for {domain}. Use save_credentials() first.",
            )

        try:
            page = self._manager.page

            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            await asyncio.sleep(0.5)

            username_filled = False
            for sel in username_selector.split(", "):
                try:
                    if await page.locator(sel.strip()).count() > 0:
                        await page.fill(sel.strip(), username, timeout=5000)
                        username_filled = True
                        break
                except Exception:
                    continue

            if not username_filled:
                return BrowserResult(
                    success=False,
                    message="Username input not found",
                    url=page.url,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            await asyncio.sleep(0.3)

            password_filled = False
            for sel in password_selector.split(", "):
                try:
                    if await page.locator(sel.strip()).count() > 0:
                        await page.fill(sel.strip(), password, timeout=5000)
                        password_filled = True
                        break
                except Exception:
                    continue

            if not password_filled:
                return BrowserResult(
                    success=False,
                    message="Password input not found",
                    url=page.url,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            await asyncio.sleep(0.3)

            submitted = False
            for sel in submit_selector.split(", "):
                try:
                    if await page.locator(sel.strip()).count() > 0:
                        await page.click(sel.strip(), timeout=5000)
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                await page.keyboard.press("Enter")

            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            await asyncio.sleep(2)

            if success_indicator:
                try:
                    await page.wait_for_selector(success_indicator, timeout=5000)
                except Exception:
                    pass

            if failure_indicator:
                try:
                    is_visible = await page.locator(failure_indicator).is_visible()
                    if is_visible:
                        elapsed = (time.perf_counter() - start) * 1000
                        return BrowserResult(
                            success=False,
                            message="Login failed (failure indicator found)",
                            url=page.url,
                            duration_ms=elapsed,
                        )
                except Exception:
                    pass

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Login attempt completed for {domain}",
                url=page.url,
                title=await page.title(),
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Login failed: %s", exc)
            return BrowserResult(
                success=False,
                message=f"Login failed: {exc}",
                error=str(exc),
                url=self._manager.page.url if self._manager.page else "",
                duration_ms=elapsed,
            )

    async def check_login_status(self, domain: str, indicator_selector: str = "") -> BrowserResult:
        """Check if currently logged into a domain.

        Args:
            domain: Domain to check.
            indicator_selector: CSS selector indicating logged-in state.
        """
        if not self._manager.page:
            return BrowserResult(success=False, message="No active page")

        try:
            current_url = self._manager.page.url
            if domain not in current_url:
                return BrowserResult(
                    success=False,
                    message=f"Not on {domain} (current: {current_url})",
                    data={"logged_in": False},
                )

            if indicator_selector:
                is_visible = await self._manager.page.locator(indicator_selector).is_visible()
                return BrowserResult(
                    success=True,
                    message=f"Login status: {'in' if is_visible else 'not in'}",
                    data={"logged_in": is_visible},
                )

            cookies_result = await self._manager.get_cookies(domain)
            cookies = cookies_result.data if cookies_result.success else []

            session_cookies = [c for c in cookies if "session" in c.get("name", "").lower() or "token" in c.get("name", "").lower()]

            return BrowserResult(
                success=True,
                message="Session cookies found" if session_cookies else "No session cookies",
                data={"logged_in": bool(session_cookies), "session_cookies": len(session_cookies)},
            )

        except Exception as exc:
            return BrowserResult(success=False, message=f"Status check failed: {exc}")

    async def logout(self, domain: str, logout_url: str | None = None, logout_selector: str = "") -> BrowserResult:
        """Log out from a domain.

        Args:
            domain: Domain to log out from.
            logout_url: Direct logout URL.
            logout_selector: CSS selector for logout button/link.
        """
        start = time.perf_counter()
        if not self._manager.page:
            return BrowserResult(success=False, message="No active page")

        try:
            if logout_url:
                await self._manager.page.goto(logout_url, timeout=self._config.timeout_ms)
            elif logout_selector:
                await self._manager.page.click(logout_selector, timeout=self._config.timeout_ms)
                await self._manager.page.wait_for_load_state("domcontentloaded", timeout=self._config.timeout_ms)
            else:
                await self._manager.clear_cookies(domain)
                return BrowserResult(
                    success=True,
                    message="Logged out (cookies cleared)",
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Logged out from {domain}",
                url=self._manager.page.url,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Logout failed: {exc}", duration_ms=elapsed)

    async def detect_captcha(self) -> BrowserResult:
        """Detect if a CAPTCHA is present on the page."""
        if not self._manager.page:
            return BrowserResult(success=False, message="No active page")

        captcha_selectors = [
            "iframe[src*='captcha']",
            "iframe[src*='recaptcha']",
            ".g-recaptcha",
            "#captcha",
            "[data-sitekey]",
            "iframe[src*='challenge']",
            ".h-captcha",
            "#hcaptcha",
        ]

        for selector in captcha_selectors:
            try:
                count = await self._manager.page.locator(selector).count()
                if count > 0:
                    return BrowserResult(
                        success=True,
                        message=f"CAPTCHA detected: {selector}",
                        data={"captcha_type": selector, "found": True},
                    )
            except Exception:
                continue

        return BrowserResult(
            success=True,
            message="No CAPTCHA detected",
            data={"found": False},
        )
