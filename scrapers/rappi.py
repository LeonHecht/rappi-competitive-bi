"""Rappi scraper adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page
else:
    Page = object

from scrapers.base import Address, BaseScraper, ProductQuery, ScrapeResult
from scrapers.utils import retry_async


class RappiScraper(BaseScraper):
    platform_name = "rappi"
    base_url = "https://www.rappi.com.mx/"

    @retry_async()
    async def set_address(self, page: Page, address: Address) -> None:
        # TODO: Implement Rappi-specific address selectors and confirmation flow.
        raise NotImplementedError("Rappi address flow is pending selector implementation.")

    @retry_async()
    async def search_product(self, page: Page, product: ProductQuery) -> None:
        # TODO: Implement Rappi-specific product search selectors.
        raise NotImplementedError("Rappi product search is pending selector implementation.")

    @retry_async()
    async def extract_results(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
    ) -> list[ScrapeResult]:
        # TODO: Implement Rappi-specific result extraction and normalization.
        raise NotImplementedError("Rappi result extraction is pending selector implementation.")
