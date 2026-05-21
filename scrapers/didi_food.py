"""DiDi Food scraper adapter."""

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


class DidiFoodScraper(BaseScraper):
    platform_name = "didi_food"
    base_url = "https://www.didi-food.com/es-MX/food/"

    async def scrape(self, address: Address, product: ProductQuery) -> list[ScrapeResult]:
        page = await self.context.new_page()
        try:
            await self.open_home(page)
            await self.accept_popups(page)
            await self.set_address(page, address)
            await self.open_best_matching_merchant(page)
            results = await self.extract_results(page, address, product)
            await self.capture_address_screenshot(page, address)
            return results
        except Exception as exc:  # noqa: BLE001 - DiDi failures should not stop other rows.
            self.logger.exception(
                "DiDi Food scrape failed",
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
        self.logger.info("Setting DiDi Food address", extra={"address_id": address.id})
        address_text = format_address(address)

        await self.click_if_visible(
            page,
            [
                page.get_by_text(re.compile("ingresa direcci[oó]n de entrega", re.I)).first,
                page.locator("input[placeholder='Ingresa dirección de entrega']").first,
                page.locator("input[placeholder*='entrega' i]").first,
                page.locator("div").filter(has_text=re.compile("ingresa direcci[oó]n de entrega", re.I)).first,
            ],
            timeout_ms=1500,
        )

        address_input = await first_visible(
            [
                page.get_by_placeholder(re.compile("ingresa direcci[oó]n de entrega", re.I)),
                page.locator("input[placeholder='Ingresa dirección de entrega']").first,
                page.locator("input[placeholder*='entrega' i]").first,
                page.get_by_role("textbox").first,
                page.locator("input[placeholder*='dirección' i]").first,
                page.locator("input[placeholder*='direccion' i]").first,
                page.locator("input[placeholder*='address' i]").first,
                page.locator("input[autocomplete='street-address']"),
                page.locator("input[name*='address' i]"),
                page.locator("input").first,
            ],
            timeout_ms=5000,
        )
        if address_input is None:
            await self.raise_if_login_wall(page)
            raise RuntimeError("Could not find DiDi Food address input.")

        await address_input.click(timeout=3000)
        await address_input.fill(address_text, timeout=3000)
        await page.wait_for_timeout(1200)

        suggestion = await first_visible(
            [
                page.get_by_text(re.compile(re.escape(address.street.split(",")[0]), re.I)).first,
                page.get_by_text(re.compile(re.escape(address.postal_code), re.I)).first,
                page.locator("div").filter(has_text=re.compile(re.escape(address.street.split(",")[0]), re.I)).first,
                page.locator("[role='option']").filter(
                    has_text=re.compile(re.escape(address.street.split(",")[0]), re.I)
                ).first,
                page.locator("[role='listitem']").filter(
                    has_text=re.compile(re.escape(address.street.split(",")[0]), re.I)
                ).first,
            ],
            timeout_ms=5000,
        )
        if suggestion is not None:
            await click_didi(suggestion)
        else:
            await address_input.press("Enter")

        await self.click_if_visible(
            page,
            [
                page.get_by_role("button", name=re.compile("buscar comida", re.I)),
                page.locator("button").filter(has_text=re.compile("buscar comida", re.I)).first,
                page.locator("[role='button']").filter(has_text=re.compile("buscar comida", re.I)).first,
                page.get_by_text(re.compile("^\\s*buscar comida\\s*$", re.I)).first,
            ],
            timeout_ms=5000,
        )
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)

    async def search_product(self, page: Page, product: ProductQuery) -> None:
        search_control = await first_visible(
            [
                page.get_by_role("button", name=re.compile("buscar|search", re.I)),
                page.get_by_role("textbox", name=re.compile("buscar|search", re.I)),
                page.get_by_placeholder(re.compile("buscar|search", re.I)),
            ],
            timeout_ms=2500,
        )
        if search_control is None:
            return
        await search_control.click()
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
        await page.wait_for_timeout(1500)

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
        item_text = await safe_text(item) if item is not None else ""

        store_name = await self.extract_store_name(page)
        price = parse_money(item_text)
        item_name = first_matching_line(item_text, product.name) if item_text else None
        delivery_fee = parse_labeled_money(page_text, ["envio", "entrega", "delivery"])
        service_fee = parse_labeled_money(page_text, ["servicio", "service"])
        final_total = parse_labeled_money(page_text, ["total"])
        eta = parse_eta(page_text)
        promotions = extract_promotions(page_text)

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

        return [
            ScrapeResult(
                platform=self.platform_name,
                address_id=address.id,
                product_id=product.id,
                product_name=product.name,
                store_name=store_name or MCDONALDS_QUERY,
                item_name=item_name,
                price=price,
                delivery_fee=delivery_fee,
                service_fee=service_fee,
                final_total=final_total,
                estimated_delivery_minutes=eta,
                visible_promotions=promotions,
                status="success" if not missing_fields else "partial_success",
                raw_payload={
                    "address_label": address.label,
                    "merchant_query": MCDONALDS_QUERY,
                    "missing_fields": missing_fields,
                    "limitation": "Checkout-level fees may require cart/session state and can be unavailable.",
                    "item_text": item_text[:1000],
                },
            )
        ]

    async def accept_popups(self, page: Page) -> None:
        await self.click_if_visible(
            page,
            [
                page.get_by_role("button", name=re.compile("acept|accept|permitir|allow|agree", re.I)),
                page.get_by_text(re.compile("aceptar|accept|agree", re.I)).first,
            ],
            timeout_ms=2500,
        )

    async def open_best_matching_merchant(self, page: Page) -> None:
        await self.raise_if_login_wall(page)
        self.logger.info("Searching DiDi Food merchant", extra={"merchant": MCDONALDS_QUERY})

        await self.search_marketplace(page, MCDONALDS_QUERY)

        merchant = await first_visible(
            [
                page.get_by_role("link", name=re.compile("McDonald", re.I)).first,
                page.locator("a").filter(has_text=re.compile("McDonald", re.I)).first,
                page.get_by_role("button", name=re.compile("McDonald", re.I)).first,
                page.locator("article").filter(has_text=re.compile("McDonald", re.I)).first,
                page.locator("[data-testid]").filter(has_text=re.compile("McDonald", re.I)).first,
            ],
            timeout_ms=8000,
        )
        if merchant is None:
            # Manual adjustment point: DiDi's public web search may be region-gated or
            # route differently. Inspect merchant cards and add the locator above.
            raise RuntimeError("Could not find a McDonald's merchant result on DiDi Food.")
        await merchant.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)
        await self.raise_if_login_wall(page)

    async def search_marketplace(self, page: Page, query: str) -> None:
        searchbox = await first_visible(
            [
                page.get_by_role("searchbox").first,
                page.get_by_role("textbox", name=re.compile("buscar|search|restaurante|comida", re.I)),
                page.get_by_placeholder(re.compile("buscar|search|restaurante|comida", re.I)),
                page.locator("input[type='search']").first,
                page.locator("input").first,
            ],
            timeout_ms=4000,
        )
        if searchbox is None:
            search_url = f"{self.base_url}?keyword={quote_plus(query)}"
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            return

        await searchbox.click(timeout=2500)
        await searchbox.fill(query, timeout=2500)
        await searchbox.press("Enter")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)

    async def find_product_item(self, page: Page, product: ProductQuery) -> Locator | None:
        product_pattern = re.compile(re.escape(product.name), re.I)
        item = await first_visible(
            [
                page.get_by_role("button", name=product_pattern).first,
                page.get_by_role("link", name=product_pattern).first,
                page.locator("li").filter(has_text=product_pattern).first,
                page.locator("article").filter(has_text=product_pattern).first,
                page.locator("[data-testid]").filter(has_text=product_pattern).first,
                page.get_by_text(product_pattern).first,
            ],
            timeout_ms=5000,
        )
        if item is not None:
            return item
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

    async def raise_if_login_wall(self, page: Page) -> None:
        text = await safe_text(page.locator("body"))
        if re.search(
            "inicia sesi[oó]n para|iniciar sesi[oó]n para|log in to|sign in to|"
            "contin[uú]a con|continuar con|necesitas iniciar",
            text,
            re.I,
        ):
            raise RuntimeError(
                "DiDi Food appears to require login. Re-run with --user-data-dir .browser-profile "
                "and complete login manually in the persistent browser profile."
            )

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
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Could not capture DiDi Food error screenshot", extra={"error": repr(exc)})

    async def click_if_visible(self, page: Page, locators: list[Locator], timeout_ms: int) -> bool:
        locator = await first_visible(locators, timeout_ms=timeout_ms)
        if locator is None:
            return False
        await click_didi(locator)
        return True


def format_address(address: Address) -> str:
    return f"{address.street}, {address.city}, {address.state}, {address.postal_code}, {address.country}"


async def click_didi(locator: Locator) -> None:
    try:
        await locator.click(timeout=3000)
        return
    except Exception:
        pass

    try:
        await locator.click(timeout=3000, force=True)
        return
    except Exception:
        pass

    await locator.evaluate(
        """(element) => {
            const clickable = element.closest('button,[role="button"],a') || element;
            clickable.click();
        }"""
    )
