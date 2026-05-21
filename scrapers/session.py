"""Browser session management for scraper runs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, async_playwright


@asynccontextmanager
async def browser_session(
    *,
    headless: bool,
    timeout_ms: int,
    user_data_dir: Path | None = None,
) -> AsyncIterator[BrowserContext]:
    """Create either an ephemeral or persistent Chromium context."""

    async with async_playwright() as playwright:
        browser: Browser | None = None
        if user_data_dir is not None:
            user_data_dir.mkdir(parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=headless,
            )
        else:
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context()

        context.set_default_timeout(timeout_ms)
        try:
            yield context
        finally:
            await context.close()
            if browser is not None:
                await browser.close()

