"""Shared scraper interfaces and browser workflow primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page
else:
    BrowserContext = Any
    Page = Any

from scrapers.utils import capture_screenshot, retry_async

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Address:
    """Search location used to collect marketplace results."""

    id: str
    label: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "MX"


@dataclass(frozen=True)
class ProductQuery:
    """Product or keyword requested from each platform."""

    id: str
    name: str
    category: str | None = None
    notes: str | None = None


@dataclass
class ScrapeResult:
    """Normalized item returned by any platform adapter."""

    platform: str
    address_id: str
    product_id: str
    product_name: str
    store_name: str | None = None
    item_name: str | None = None
    price: float | None = None
    currency: str = "MXN"
    delivery_fee: float | None = None
    service_fee: float | None = None
    final_total: float | None = None
    estimated_delivery_minutes: int | None = None
    rating: float | None = None
    visible_promotions: list[str] | None = None
    status: str = "success"
    error: str | None = None
    raw_payload: dict[str, Any] | None = None
    scraped_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload["scraped_at"]:
            payload["scraped_at"] = datetime.now(UTC).isoformat()
        return payload


class BaseScraper(ABC):
    """Base contract and workflow for all platform-specific scrapers."""

    platform_name: str
    base_url: str

    def __init__(self, context: BrowserContext, screenshot_dir: Path) -> None:
        self.context = context
        self.screenshot_dir = screenshot_dir
        self.logger = logging.getLogger(f"{self.__module__}.{self.__class__.__name__}")

    async def scrape(self, address: Address, product: ProductQuery) -> list[ScrapeResult]:
        """Run a complete scrape flow for one address and one product query."""

        page = await self.context.new_page()
        try:
            self.logger.info(
                "Opening platform",
                extra={
                    "platform": self.platform_name,
                    "address_id": address.id,
                    "product_id": product.id,
                },
            )
            await self.open_home(page)
            await self.set_address(page, address)
            await self.search_product(page, product)
            results = await self.extract_results(page, address, product)
            await self.capture_screenshot(page, address, product)
            return results
        except Exception:
            await self.capture_screenshot(page, address, product, suffix="error")
            raise
        finally:
            await page.close()

    @retry_async()
    async def open_home(self, page: Page) -> None:
        await page.goto(self.base_url, wait_until="domcontentloaded")

    async def capture_screenshot(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
        suffix: str = "result",
    ) -> Path:
        """Capture a screenshot using the standard project naming convention."""

        return await capture_screenshot(
            page,
            self.screenshot_dir,
            f"{self.platform_name}_{address.id}_{product.id}_{suffix}",
        )

    @abstractmethod
    async def set_address(self, page: Page, address: Address) -> None:
        """Set the delivery address for the current platform."""

    @abstractmethod
    async def search_product(self, page: Page, product: ProductQuery) -> None:
        """Search the target product or keyword on the current platform."""

    @abstractmethod
    async def extract_results(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
    ) -> list[ScrapeResult]:
        """Extract normalized results from the current platform."""


PlatformScraper = BaseScraper
