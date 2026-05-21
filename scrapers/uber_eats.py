"""Uber Eats scraper adapter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page
else:
    Locator = object
    Page = object

from scrapers.base import Address, BaseScraper, ProductQuery, ScrapeResult
from scrapers.page_helpers import (
    clean_text,
    extract_promotions,
    first_matching_line,
    first_visible,
    parse_eta,
    parse_labeled_money,
    parse_money,
    product_token_pattern,
    safe_text,
)
from scrapers.utils import retry_async

MCDONALDS_QUERY = "McDonald's"


class UberEatsScraper(BaseScraper):
    platform_name = "uber_eats"
    base_url = "https://www.ubereats.com/mx"

    async def scrape(self, address: Address, product: ProductQuery) -> list[ScrapeResult]:
        """Scrape one product from the best matching McDonald's merchant.

        Uber Eats changes markup frequently. The helpers below prefer role, placeholder,
        and visible text locators, then fall back to URL/search heuristics. When a manual
        adjustment is needed, it should usually be isolated to the selector lists in this
        file rather than the orchestration code.
        """

        page = await self.context.new_page()
        try:
            await self.open_home(page)
            await self.accept_cookie_banner(page)
            await self.set_address(page, address)
            await self.open_best_matching_merchant(page)
            result = await self.extract_results(page, address, product)
            await self.capture_address_screenshot(page, address)
            return result
        except Exception as exc:  # noqa: BLE001 - one address/product must not stop the run.
            self.logger.exception(
                "Uber Eats scrape failed",
                extra={"address_id": address.id, "product_id": product.id},
            )
            await self.safe_error_screenshot(page, address, product)
            return [
                ScrapeResult(
                    platform=self.platform_name,
                    address_id=address.id,
                    product_id=product.id,
                    product_name=product.name,
                    store_name=MCDONALDS_QUERY,
                    status="failed",
                    error=str(exc),
                    raw_payload={"address_label": address.label},
                )
            ]
        finally:
            await page.close()

    @retry_async()
    async def set_address(self, page: Page, address: Address) -> None:
        address_text = format_address(address)
        self.logger.info("Setting Uber Eats address", extra={"address_id": address.id})

        address_inputs = [
            page.get_by_role("textbox", name=re.compile("direcci[oó]n|address|entrega|delivery", re.I)),
            page.get_by_placeholder(re.compile("direcci[oó]n|address|entrega|delivery|ingresa", re.I)),
            page.locator("input[autocomplete='street-address']"),
            page.locator("input[name*='address' i]"),
            page.locator("input").first,
        ]
        address_input = await first_visible(address_inputs, timeout_ms=5000)
        if address_input is None:
            # Manual adjustment point: inspect the landing page and add the new address
            # textbox locator above if Uber changes its public address form.
            raise RuntimeError("Could not find Uber Eats address input.")

        await address_input.click()
        await address_input.fill(address_text)
        await page.wait_for_timeout(1200)

        suggestion = await first_visible(
            [
                page.get_by_role("option").filter(has_text=re.compile(address.street, re.I)).first,
                page.get_by_role("listitem").filter(has_text=re.compile(address.street, re.I)).first,
                page.locator("[role='option']").first,
                page.locator("[role='listitem']").first,
                page.get_by_text(re.compile(re.escape(address.street), re.I)).first,
            ],
            timeout_ms=5000,
        )
        if suggestion is not None:
            await suggestion.click()
        else:
            await address_input.press("Enter")

        await self.click_if_visible(
            page,
            [
                page.get_by_role("button", name=re.compile("listo|done|confirm|guardar|save", re.I)),
                page.get_by_role("button", name=re.compile("entregar aqu[ií]|deliver here", re.I)),
            ],
            timeout_ms=2500,
        )
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1500)

    async def search_product(self, page: Page, product: ProductQuery) -> None:
        """Search within an already-open merchant page when the menu search UI exists."""

        search_controls = [
            page.get_by_role("button", name=re.compile("buscar|search", re.I)),
            page.get_by_role("textbox", name=re.compile("buscar|search", re.I)),
            page.get_by_placeholder(re.compile("buscar|search", re.I)),
        ]
        control = await first_visible(search_controls, timeout_ms=2500)
        if control is None:
            return

        await control.click()
        textbox = await first_visible(
            [
                page.get_by_role("textbox", name=re.compile("buscar|search", re.I)),
                page.get_by_placeholder(re.compile("buscar|search", re.I)),
                page.locator("input[type='search']").first,
                page.locator("input").last,
            ],
            timeout_ms=2500,
        )
        if textbox is None:
            return
        await textbox.fill(product.name)
        await textbox.press("Enter")
        await page.wait_for_timeout(1200)

    @retry_async()
    async def extract_results(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
    ) -> list[ScrapeResult]:
        await self.search_product(page, product)
        item = await self.find_product_item(page, product)
        page_text = await safe_text(page.locator("body"))

        store_name = await self.extract_store_name(page)
        eta = parse_eta(page_text)
        delivery_fee = parse_labeled_money(page_text, ["envio", "entrega", "delivery"])
        service_fee = parse_labeled_money(page_text, ["servicio", "service"])
        final_total = parse_labeled_money(page_text, ["total"])
        promotions = extract_promotions(page_text)

        item_text = await safe_text(item) if item is not None else ""
        price = parse_money(item_text)
        item_name = first_matching_line(item_text, product.name) if item_text else None

        missing_fields = [
            field
            for field, value in {
                "item_name": item_name,
                "price": price,
                "estimated_delivery_minutes": eta,
                "delivery_fee": delivery_fee,
                "service_fee": service_fee,
                "final_total": final_total,
            }.items()
            if value is None
        ]
        status = "success" if not missing_fields else "partial_success"

        return [
            ScrapeResult(
                platform=self.platform_name,
                address_id=address.id,
                product_id=product.id,
                product_name=product.name,
                store_name=store_name or MCDONALDS_QUERY,
                item_name=item_name,
                price=price,
                currency="MXN",
                delivery_fee=delivery_fee,
                service_fee=service_fee,
                final_total=final_total,
                estimated_delivery_minutes=eta,
                visible_promotions=promotions,
                status=status,
                raw_payload={
                    "address_label": address.label,
                    "merchant_query": MCDONALDS_QUERY,
                    "missing_fields": missing_fields,
                    "item_text": item_text[:1000],
                },
            )
        ]

    async def accept_cookie_banner(self, page: Page) -> None:
        await self.click_if_visible(
            page,
            [
                page.get_by_role("button", name=re.compile("acept|accept|allow|permitir", re.I)),
                page.get_by_text(re.compile("aceptar|accept", re.I)).first,
            ],
            timeout_ms=2500,
        )

    async def open_best_matching_merchant(self, page: Page) -> None:
        self.logger.info("Searching Uber Eats merchant", extra={"merchant": MCDONALDS_QUERY})
        search_url = f"{self.base_url}/search?q={quote_plus(MCDONALDS_QUERY)}"
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        merchant_link = await first_visible(
            [
                page.get_by_role("link", name=re.compile("McDonald", re.I)).first,
                page.locator("a").filter(has_text=re.compile("McDonald", re.I)).first,
                page.locator("a[href*='/store/']").filter(has_text=re.compile("McDonald", re.I)).first,
            ],
            timeout_ms=7000,
        )
        if merchant_link is None:
            # Manual adjustment point: if search results stop exposing merchant cards as
            # links, inspect the card wrapper and add a role/text locator here.
            raise RuntimeError("Could not find a McDonald's merchant result.")

        await merchant_link.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

    async def find_product_item(self, page: Page, product: ProductQuery) -> Locator | None:
        product_pattern = re.compile(re.escape(product.name), re.I)
        candidates = [
            page.get_by_role("button", name=product_pattern).first,
            page.get_by_role("link", name=product_pattern).first,
            page.locator("li").filter(has_text=product_pattern).first,
            page.locator("article").filter(has_text=product_pattern).first,
            page.locator("[data-testid]").filter(has_text=product_pattern).first,
            page.get_by_text(product_pattern).first,
        ]
        item = await first_visible(candidates, timeout_ms=5000)
        if item is not None:
            return item

        # Manual adjustment point: product names in config may not match Uber Eats menu
        # copy exactly. Add synonyms in config/products.yaml notes or broaden this matcher.
        token_pattern = product_token_pattern(product.name)
        if token_pattern is None:
            return None
        return await first_visible(
            [
                page.locator("li").filter(has_text=token_pattern).first,
                page.locator("article").filter(has_text=token_pattern).first,
                page.get_by_text(token_pattern).first,
            ],
            timeout_ms=3000,
        )

    async def extract_store_name(self, page: Page) -> str | None:
        heading = await first_visible(
            [
                page.get_by_role("heading", name=re.compile("McDonald", re.I)).first,
                page.locator("h1").first,
            ],
            timeout_ms=2500,
        )
        return clean_text(await safe_text(heading)) if heading is not None else None

    async def capture_address_screenshot(self, page: Page, address: Address) -> Path:
        return await self.capture_screenshot(
            page,
            address,
            ProductQuery(id="mcdonalds", name=MCDONALDS_QUERY),
            suffix="address",
        )

    async def safe_error_screenshot(self, page: Page, address: Address, product: ProductQuery) -> None:
        try:
            await self.capture_screenshot(page, address, product, suffix="error")
        except Exception as exc:  # noqa: BLE001 - screenshot failure should not mask scrape failure.
            self.logger.warning("Could not capture error screenshot", extra={"error": repr(exc)})

    async def click_if_visible(self, page: Page, locators: list[Locator], timeout_ms: int) -> bool:
        locator = await first_visible(locators, timeout_ms=timeout_ms)
        if locator is None:
            return False
        await locator.click()
        return True


def format_address(address: Address) -> str:
    return f"{address.street}, {address.city}, {address.state}, {address.postal_code}, {address.country}"
