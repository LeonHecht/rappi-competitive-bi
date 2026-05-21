"""Uber Eats scraper adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page
else:
    Page = object

from scrapers.base import Address, BaseScraper, ProductQuery, ScrapeResult
from scrapers.utils import retry_async


class UberEatsScraper(BaseScraper):
    platform_name = "uber_eats"
    base_url = "https://www.ubereats.com/mx"

    @retry_async()
    async def set_address(self, page: Page, address: Address) -> None:
        # TODO: Implement Uber Eats-specific address selectors and confirmation flow.
        raise NotImplementedError("Uber Eats address flow is pending selector implementation.")

    @retry_async()
    async def search_product(self, page: Page, product: ProductQuery) -> None:
        # TODO: Implement Uber Eats-specific product search selectors.
        raise NotImplementedError("Uber Eats product search is pending selector implementation.")

    @retry_async()
    async def extract_results(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
    ) -> list[ScrapeResult]:
        # TODO: Implement Uber Eats-specific result extraction and normalization.
        raise NotImplementedError("Uber Eats result extraction is pending selector implementation.")
