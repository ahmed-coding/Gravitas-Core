"""
Browser Automation Engine — UI-level verification and observability.

Controlled navigation and interaction (Playwright); screenshot and DOM snapshot;
Javascript console error streaming; deterministic viewport/device profiles.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

from .memory import _tool_result

# Optional: only load playwright when used
_playwright = None

# Order: try system Chrome/Edge first so no "playwright install chromium" is required
_BROWSER_CHANNELS = ["chrome", "msedge","firefox", "chromium"]


def _get_playwright():
    global _playwright
    if _playwright is None:
        try:
            from playwright.async_api import async_playwright
            _playwright = async_playwright
        except ImportError:
            raise ImportError(
                "playwright is required. Install with: pip install playwright. "
                "Chrome/Edge already on your system are used when available; otherwise run: playwright install chromium"
            )
    return _playwright


async def _launch_any_available_browser(playwright):
    """Launch first available browser: system Chrome, Edge, or Playwright Chromium."""
    pw = playwright
    last_error = None
    for channel in _BROWSER_CHANNELS:
        try:
            if channel == "chromium":
                # Playwright's bundled Chromium (may require: playwright install chromium)
                browser = await pw.chromium.launch(headless=False)  # Visible browser
            else:
                # System-installed browser (no extra install)
                browser = await pw.chromium.launch(headless=False, channel=channel)  # Visible browser
            return browser, channel
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(
        "No browser available. Install Chrome/Edge, or run: playwright install chromium"
    ) from last_error


class BrowserEngine:
    """
    Playwright-based browser automation: uses system Chrome/Edge when available,
    otherwise Playwright's Chromium. No mandatory 'playwright install' if Chrome/Edge exists.
    """

    def __init__(self, project_root: str | Path | None = None):
        import os
        self._root = Path(project_root or os.getcwd()).resolve()
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._console_errors: list[str] = []
        self._browser_channel: str | None = None

    async def _ensure_browser(self) -> None:
        if self._browser is None:
            pw = _get_playwright()
            self._pw = await pw().start()
            self._browser, self._browser_channel = await _launch_any_available_browser(self._pw)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Gravitas-Core-MCP/1.0 (Playwright)",
            )
            self._page = await self._context.new_page()
            self._console_errors = []

            def on_console(msg):
                if msg.type == "error":
                    self._console_errors.append(msg.text)

            self._page.on("console", on_console)

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict[str, Any]:
        """Navigate to URL and optionally wait. wait_until: load, domcontentloaded, networkidle."""
        try:
            await self._ensure_browser()
            self._console_errors = []
            await self._page.goto(url, wait_until=wait_until, timeout=30000)
            return _tool_result(
                "success",
                observations={
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "console_errors": list(self._console_errors),
                },
                next_recommended_action="Use snapshot or screenshot to verify page.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Check URL and network.",
            )

    async def snapshot(self) -> dict[str, Any]:
        """Capture DOM snapshot (accessibility tree) and console errors."""
        try:
            await self._ensure_browser()
            tree = await self._page.accessibility.snapshot()
            return _tool_result(
                "success",
                observations={
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "accessibility_tree": tree,
                    "console_errors": list(self._console_errors),
                },
                next_recommended_action="Inspect tree and errors for verification.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Ensure page is loaded; navigate first.",
            )

    async def screenshot(self, path: str | Path | None = None) -> dict[str, Any]:
        """Take screenshot; save to path if provided, else return base64 in observations."""
        try:
            await self._ensure_browser()
            if path:
                out = Path(path)
                if not out.is_absolute():
                    out = self._root / out
                out.parent.mkdir(parents=True, exist_ok=True)
                await self._page.screenshot(path=str(out))
                return _tool_result(
                    "success",
                    observations={"path": str(out), "url": self._page.url},
                    next_recommended_action="Inspect screenshot for UI verification.",
                )
            buf = await self._page.screenshot()
            b64 = base64.standard_b64encode(buf).decode("ascii")
            return _tool_result(
                "success",
                observations={"image_base64": b64[:200] + "...", "url": self._page.url, "console_errors": list(self._console_errors)},
                next_recommended_action="Use snapshot for full DOM or save to file next time.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Ensure page is loaded; navigate first.",
            )

    async def get_console_errors(self) -> dict[str, Any]:
        """Return collected JS console errors since last navigate."""
        await self._ensure_browser()
        return _tool_result(
            "success",
            observations={"console_errors": list(self._console_errors), "url": self._page.url},
            next_recommended_action="Fix reported errors in code.",
        )

    async def hover(self, selector: str) -> dict[str, Any]:
        """Hover over an element by CSS selector."""
        try:
            await self._ensure_browser()
            await self._page.hover(selector, timeout=30000)
            return _tool_result(
                "success",
                observations={"selector": selector, "url": self._page.url},
                next_recommended_action="Element hovered successfully.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Check selector and ensure page is loaded.",
            )
