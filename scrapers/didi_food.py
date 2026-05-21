"""DiDi Food scraper adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page
else:
    Page = object

from scrapers.base import Address, BaseScraper, ProductQuery, ScrapeResult
from scrapers.utils import retry_async


class DidiFoodScraper(BaseScraper):
    platform_name = "didi_food"
    base_url = "https://web.didiglobal.com/mx/food/"

    @retry_async()
    async def set_address(self, page: Page, address: Address) -> None:
        # TODO: Implement DiDi Food-specific address selectors and confirmation flow.
        raise NotImplementedError("DiDi Food address flow is pending selector implementation.")

    @retry_async()
    async def search_product(self, page: Page, product: ProductQuery) -> None:
        # TODO: Implement DiDi Food-specific product search selectors.
        raise NotImplementedError("DiDi Food product search is pending selector implementation.")

    @retry_async()
    async def extract_results(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
    ) -> list[ScrapeResult]:
        # TODO: Implement DiDi Food-specific result extraction and normalization.
        raise NotImplementedError("DiDi Food result extraction is pending selector implementation.")
