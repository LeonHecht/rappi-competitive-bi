"""Reusable scraper utilities."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from playwright.async_api import Page
else:
    Page = Any

P = ParamSpec("P")
T = TypeVar("T")


def retry_async(
    attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff: float = 2.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry async scraper operations with exponential backoff."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger = logging.getLogger(func.__module__)
            wait_time = delay_seconds
            last_error: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except NotImplementedError:
                    raise
                except Exception as exc:  # noqa: BLE001 - scraper failures are retried generically.
                    last_error = exc
                    logger.warning(
                        "Retryable scraper error",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "attempts": attempts,
                            "error": repr(exc),
                        },
                    )
                    if attempt < attempts:
                        await asyncio.sleep(wait_time)
                        wait_time *= backoff
            if last_error is None:
                raise RuntimeError("Retry wrapper failed without capturing an exception.")
            raise last_error

        return wrapper

    return decorator


async def capture_screenshot(page: Page, screenshot_dir: Path, name: str) -> Path:
    """Capture a full-page screenshot for audit and debugging."""

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = screenshot_dir / f"{timestamp}_{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    return path
