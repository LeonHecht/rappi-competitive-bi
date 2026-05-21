"""Platform adapter registry."""

from __future__ import annotations

from scrapers.base import BaseScraper
from scrapers.didi_food import DidiFoodScraper
from scrapers.rappi import RappiScraper
from scrapers.uber_eats import UberEatsScraper

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    RappiScraper.platform_name: RappiScraper,
    UberEatsScraper.platform_name: UberEatsScraper,
    DidiFoodScraper.platform_name: DidiFoodScraper,
}
