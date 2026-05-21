"""Shared Playwright helper functions for platform adapters."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Locator
else:
    Locator = object

MONEY_WITH_SYMBOL_RE = re.compile(r"(?:MXN\s*)?\$\s*([0-9]+(?:[.,][0-9]{1,2})?)", re.I)
ETA_RE = re.compile(r"(\d{1,3})\s*(?:-|a|to)?\s*(\d{1,3})?\s*min", re.IGNORECASE)


async def first_visible(locators: list[Locator], timeout_ms: int) -> Locator | None:
    for locator in locators:
        try:
            await locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except Exception:
            continue
    return None


async def safe_text(locator: Locator | None) -> str:
    if locator is None:
        return ""
    try:
        return await locator.inner_text(timeout=2500)
    except Exception:
        return ""


def parse_money(text: str) -> float | None:
    """Parse currency-marked MXN amounts and avoid numbers from item names."""

    match = MONEY_WITH_SYMBOL_RE.search(text.replace(",", "."))
    if not match:
        return None
    return float(match.group(1))


def parse_labeled_money(text: str, labels: list[str]) -> float | None:
    normalized = normalize_for_matching(text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if any(label in line for label in labels):
            nearby = " ".join(lines[index : index + 3])
            value = parse_money(nearby)
            if value is not None:
                return value
            if any(token in nearby for token in ["gratis", "free", "sin costo"]):
                return 0.0
    return None


def parse_eta(text: str) -> int | None:
    match = ETA_RE.search(text)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or start)
    return round((start + end) / 2)


def extract_promotions(text: str) -> list[str]:
    keywords = re.compile("promo|promoci[oó]n|descuento|gratis|2x1|ahorra|offer|deal", re.I)
    promotions: list[str] = []
    for line in text.splitlines():
        cleaned = clean_text(line)
        if cleaned and keywords.search(cleaned) and cleaned not in promotions:
            promotions.append(cleaned)
    return promotions[:5]


def first_matching_line(text: str, product_name: str) -> str | None:
    product_pattern = re.compile(re.escape(product_name), re.I)
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for line in lines:
        if product_pattern.search(line):
            return line
    return lines[0] if lines else None


def product_token_pattern(product_name: str) -> re.Pattern[str] | None:
    product_tokens = [token for token in re.split(r"\W+", product_name.lower()) if len(token) > 2]
    if not product_tokens:
        return None
    return re.compile("|".join(re.escape(token) for token in product_tokens), re.I)


def normalize_for_matching(text: str) -> str:
    return (
        text.lower()
        .replace("í", "i")
        .replace("ó", "o")
        .replace("á", "a")
        .replace("é", "e")
        .replace("ú", "u")
    )


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

