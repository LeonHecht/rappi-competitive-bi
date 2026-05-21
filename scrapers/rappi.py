"""Rappi scraper adapter."""

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


class RappiScraper(BaseScraper):
    platform_name = "rappi"
    base_url = "https://www.rappi.com.mx/"

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
        except Exception as exc:  # noqa: BLE001 - Rappi failures should not stop other rows.
            self.logger.exception(
                "Rappi scrape failed",
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

    @retry_async(attempts=1)
    async def set_address(self, page: Page, address: Address) -> None:
        """Use the address already selected in the persistent Rappi session.

        Rappi's address-change flow is modal-heavy and fragile. For this adapter we
        intentionally avoid changing address and rely on the user to set the correct
        address manually in the persistent profile passed with `--user-data-dir`.
        """

        self.logger.info("Using existing Rappi session address", extra={"address_id": address.id})
        visible_address = await self.current_visible_address(page)
        if visible_address:
            self.logger.info(
                "Rappi visible session address",
                extra={"address_id": address.id, "visible_address": visible_address},
            )
            return

        await self.raise_if_login_wall(page)
        if await self.has_main_search(page):
            self.logger.warning(
                "Rappi address is not visible; continuing with current session state",
                extra={"address_id": address.id},
            )
            return
        raise RuntimeError(
            "Rappi has no visible address in the current session. Open Rappi with "
            "--user-data-dir .browser-profile, set the address manually, then rerun."
        )

    async def select_address_suggestion(self, page: Page, address: Address, address_input: Locator) -> None:
        """Select one address suggestion from Rappi's address search modal.

        Rappi renders suggestions as plain rows rather than always using stable option
        roles. Prefer a row containing the configured street/postal code, then fall back
        to the first suggestion that is not "Usar mi ubicación actual".
        """

        street_head = re.escape(address.street.split(",")[0])
        suggestion = await first_visible(
            [
                page.locator("[data-qa='suggestion-text']").filter(has_text=re.compile(street_head, re.I)).first,
                page.locator("[data-qa='suggestion-text']").filter(
                    has_text=re.compile(re.escape(address.postal_code), re.I)
                ).first,
                page.get_by_role("option").filter(has_text=re.compile(street_head, re.I)).first,
                page.get_by_role("listitem").filter(has_text=re.compile(street_head, re.I)).first,
                page.locator("[role='option']").filter(has_text=re.compile(street_head, re.I)).first,
                page.locator("[role='listitem']").filter(has_text=re.compile(street_head, re.I)).first,
                page.get_by_text(re.compile(street_head, re.I)).first,
            ],
            timeout_ms=3000,
        )
        if suggestion is None:
            suggestion = await first_visible(
                [
                    page.locator("[data-qa='suggestion-text']").filter(
                        has_not_text=re.compile("usar mi ubicaci[oó]n actual", re.I)
                    ).first,
                    page.locator("[role='option']").first,
                    page.locator("[role='listitem']").first,
                ],
                timeout_ms=1500,
            )

        if suggestion is not None:
            await click_suggestion(suggestion)
        else:
            await address_input.press("Enter")
        await page.wait_for_timeout(800)

    async def confirm_location_modal(self, page: Page) -> None:
        """Confirm Rappi's map verification step.

        After selecting a suggestion, Rappi commonly opens a "Verifica la ubicación"
        modal with a green "Confirmar dirección" button. Checkout-level scraping should
        not continue until this button is accepted.
        """

        verify_modal = await first_visible(
            [
                page.get_by_text(re.compile("verifica la ubicaci[oó]n", re.I)).first,
                page.locator("div").filter(has_text=re.compile("verifica la ubicaci[oó]n", re.I)).first,
            ],
            timeout_ms=4000,
        )
        if verify_modal is None:
            return

        confirm_button = await first_visible(
            [
                page.locator("button:has-text('Confirmar dirección')").first,
                page.locator("[role='button']:has-text('Confirmar dirección')").first,
                page.locator("button:has-text('Confirmar direccion')").first,
                page.locator("[role='button']:has-text('Confirmar direccion')").first,
                page.get_by_role("button", name=re.compile("confirmar direcci[oó]n", re.I)),
                page.locator("[role='button']").filter(has_text=re.compile("confirmar direcci[oó]n", re.I)).first,
                page.locator("button").filter(has_text=re.compile("confirmar direcci[oó]n", re.I)).first,
                page.get_by_text(re.compile("^\\s*confirmar direcci[oó]n\\s*$", re.I)).first,
            ],
            timeout_ms=4000,
        )
        if confirm_button is None:
            raise RuntimeError("Rappi location verification modal opened, but Confirmar dirección was not found.")

        await click_suggestion(confirm_button)
        await page.wait_for_timeout(1200)
        if await self.has_open_location_modal(page):
            raise RuntimeError("Rappi location verification modal is still open after clicking Confirmar dirección.")

    async def save_address_details_modal(self, page: Page) -> None:
        """Save Rappi's optional address-details step.

        After the map confirmation, Rappi can show an "Agregar dirección" modal with
        optional apartment/label fields. We leave optional fields empty and click the
        green "Guardar dirección" button.
        """

        details_modal = await first_visible(
            [
                page.get_by_text(re.compile("agregar direcci[oó]n", re.I)).first,
                page.locator(".chakra-modal__content-container").filter(
                    has_text=re.compile("guardar direcci[oó]n", re.I)
                ).first,
            ],
            timeout_ms=2500,
        )
        if details_modal is None:
            return

        save_button = await first_visible(
            [
                page.locator("button:has-text('Guardar dirección')").first,
                page.locator("[role='button']:has-text('Guardar dirección')").first,
                page.locator("button:has-text('Guardar direccion')").first,
                page.locator("[role='button']:has-text('Guardar direccion')").first,
                page.get_by_role("button", name=re.compile("guardar direcci[oó]n", re.I)),
                page.locator("button").filter(has_text=re.compile("guardar direcci[oó]n", re.I)).first,
                page.locator("[role='button']").filter(has_text=re.compile("guardar direcci[oó]n", re.I)).first,
                page.get_by_text(re.compile("^\\s*guardar direcci[oó]n\\s*$", re.I)).first,
            ],
            timeout_ms=3000,
        )
        if save_button is None:
            raise RuntimeError("Rappi address-details modal opened, but Guardar dirección was not found.")

        await click_suggestion(save_button)
        await page.wait_for_timeout(1200)
        if await self.has_open_address_details_modal(page):
            raise RuntimeError("Rappi address-details modal is still open after clicking Guardar dirección.")

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

    @retry_async(attempts=1)
    async def extract_results(
        self,
        page: Page,
        address: Address,
        product: ProductQuery,
    ) -> list[ScrapeResult]:
        await self.raise_if_rappi_error_page(page)
        await self.search_product(page, product)
        item = await self.find_product_item(page, product)
        page_text = await safe_text(page.locator("body"))
        if is_rappi_error_text(page_text):
            raise RuntimeError(
                "Rappi returned its 500 error page before product extraction. "
                "No reliable menu data is available for this session."
            )
        item_text = await safe_text(item) if item is not None else ""

        store_name = await self.extract_store_name(page)
        price = parse_money(item_text)
        item_name = first_matching_line(item_text, product.name) if item_text else None
        parsed_item_name, parsed_price, parsed_item_text = parse_rappi_menu_item(page_text)
        if parsed_item_name is not None:
            item_name = parsed_item_name
        if parsed_price is not None:
            price = parsed_price
        if parsed_item_text:
            item_text = parsed_item_text
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
                page.get_by_role("button", name=re.compile("acept|accept|permitir|allow", re.I)),
                page.get_by_text(re.compile("aceptar|accept", re.I)).first,
            ],
            timeout_ms=2500,
        )

    async def open_best_matching_merchant(self, page: Page) -> None:
        await self.raise_if_login_wall(page)
        self.logger.info("Searching Rappi merchant", extra={"merchant": MCDONALDS_QUERY})

        await self.search_marketplace(page, MCDONALDS_QUERY)
        await self.raise_if_rappi_error_page(page)
        merchant = await self.find_merchant_card(page)
        if merchant is None:
            for search_url in [
                f"{self.base_url}search?query={quote_plus(MCDONALDS_QUERY)}",
                f"{self.base_url}mx/search?query={quote_plus(MCDONALDS_QUERY)}",
                f"{self.base_url}search?keyword={quote_plus(MCDONALDS_QUERY)}",
            ]:
                await page.goto(search_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                if await self.is_rappi_error_page(page):
                    continue
                merchant = await self.find_merchant_card(page)
                if merchant is not None:
                    break

        if merchant is None:
            # Manual adjustment point: if Rappi search URLs redirect or merchant cards are
            # no longer links/buttons, add the inspected merchant-card locator here.
            raise RuntimeError("Could not find a McDonald's merchant result on Rappi.")
        await merchant.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)
        await self.raise_if_rappi_error_page(page)
        await self.raise_if_login_wall(page)

    async def search_marketplace(self, page: Page, query: str) -> None:
        if await self.has_open_location_modal(page):
            raise RuntimeError("Rappi location verification modal is still open; cannot search marketplace.")
        if await self.has_open_address_details_modal(page):
            raise RuntimeError("Rappi address-details modal is still open; cannot search marketplace.")

        searchbox = await first_visible(
            [
                page.get_by_role("searchbox", name=re.compile("comida|restaurantes|tiendas|productos", re.I)),
                page.get_by_placeholder(re.compile("comida|restaurantes|tiendas|productos|buscar", re.I)),
                page.locator("input[type='search']").first,
            ],
            timeout_ms=3500,
        )
        if searchbox is None:
            return
        await searchbox.click(timeout=2500)
        await searchbox.fill(query, timeout=2500)
        await searchbox.press("Enter")
        await page.wait_for_timeout(1200)

        # Rappi's search submit control currently has no accessible label; it is an
        # <a role="button"> with only an SVG magnifying-glass icon. Keep this structural
        # selector close to the search input and avoid the generated class names.
        submit_button = await first_visible(
            [
                searchbox.locator("xpath=following::a[@role='button'][.//*[local-name()='svg']][1]"),
                page.locator("a[role='button']:has(svg)").last,
                page.locator("button:has(svg)").last,
            ],
            timeout_ms=1500,
        )
        if submit_button is not None:
            await submit_button.click(timeout=2500)

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1800)

    async def find_merchant_card(self, page: Page) -> Locator | None:
        merchant_pattern = re.compile("McDonald|Mc Donald", re.I)
        return await first_visible(
            [
                page.get_by_role("link", name=merchant_pattern).first,
                page.locator("a").filter(has_text=merchant_pattern).first,
                page.get_by_role("button", name=merchant_pattern).first,
                page.locator("article").filter(has_text=merchant_pattern).first,
                page.locator("[data-testid]").filter(has_text=merchant_pattern).first,
                page.get_by_text(merchant_pattern).first,
            ],
            timeout_ms=8000,
        )

    async def find_product_item(self, page: Page, product: ProductQuery) -> Locator | None:
        product_pattern = re.compile(re.escape(product.name), re.I)
        item = await first_visible_with_money(
            [
                page.get_by_role("button", name=product_pattern).first,
                page.get_by_role("link", name=product_pattern).first,
                page.locator("li").filter(has_text=product_pattern).first,
                page.locator("article").filter(has_text=product_pattern).first,
                page.locator("[data-testid]").filter(has_text=product_pattern).first,
            ],
            timeout_ms=5000,
        )
        if item is not None:
            return item
        token_pattern = product_token_pattern(product.name)
        if token_pattern is None:
            return None
        return await first_visible_with_money(
            [
                page.locator("li").filter(has_text=token_pattern).first,
                page.locator("article").filter(has_text=token_pattern).first,
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
                "Rappi appears to require login. Re-run with --user-data-dir .browser-profile "
                "and complete login manually in the persistent browser profile."
            )

    async def is_rappi_error_page(self, page: Page) -> bool:
        text = await safe_text(page.locator("body"))
        return is_rappi_error_text(text)

    async def has_open_location_modal(self, page: Page) -> bool:
        modal = await first_visible(
            [
                page.locator(".chakra-modal__content-container").filter(
                    has_text=re.compile("verifica la ubicaci[oó]n|confirmar direcci[oó]n", re.I)
                ).first,
                page.get_by_text(re.compile("verifica la ubicaci[oó]n", re.I)).first,
            ],
            timeout_ms=500,
        )
        return modal is not None

    async def has_open_address_details_modal(self, page: Page) -> bool:
        modal = await first_visible(
            [
                page.locator(".chakra-modal__content-container").filter(
                    has_text=re.compile("agregar direcci[oó]n|guardar direcci[oó]n", re.I)
                ).first,
                page.get_by_text(re.compile("agregar direcci[oó]n", re.I)).first,
            ],
            timeout_ms=500,
        )
        return modal is not None

    async def raise_if_rappi_error_page(self, page: Page) -> None:
        if await self.is_rappi_error_page(page):
            raise RuntimeError(
                "Rappi returned its 500 error page while searching/opening McDonald's. "
                "This is a platform-side route/session failure; retry with --user-data-dir "
                ".browser-profile after confirming the address manually."
            )

    async def has_main_search(self, page: Page) -> bool:
        search = await first_visible(
            [
                page.get_by_role("searchbox", name=re.compile("comida|restaurantes|tiendas|productos", re.I)),
                page.get_by_placeholder(re.compile("comida|restaurantes|tiendas|productos", re.I)),
                page.locator("input[type='search']").first,
            ],
            timeout_ms=2000,
        )
        return search is not None

    async def current_visible_address(self, page: Page) -> str | None:
        container = await first_visible(
            [
                page.locator("[data-qa='address-container']").first,
                page.locator("[data-qa='address-container'] [data-testid='typography']").first,
            ],
            timeout_ms=2500,
        )
        text = clean_text(await safe_text(container))
        return text or None

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
            self.logger.warning("Could not capture Rappi error screenshot", extra={"error": repr(exc)})

    async def click_if_visible(self, page: Page, locators: list[Locator], timeout_ms: int) -> bool:
        locator = await first_visible(locators, timeout_ms=timeout_ms)
        if locator is None:
            return False
        await locator.click()
        return True


def format_address(address: Address) -> str:
    return f"{address.street}, {address.city}, {address.state}, {address.postal_code}, {address.country}"


def address_matches_config(visible_address: str, address: Address) -> bool:
    normalized = normalize_address_text(visible_address)
    required_parts = [
        normalize_address_text(address.street.split(",")[0]),
        normalize_address_text(address.postal_code),
    ]
    return all(part and part in normalized for part in required_parts)


def normalize_address_text(text: str) -> str:
    return (
        text.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )


def parse_rappi_menu_item(page_text: str) -> tuple[str | None, float | None, str]:
    """Extract the first visible menu item near a currency amount from Rappi text."""

    lines = [clean_text(line) for line in page_text.splitlines() if clean_text(line)]
    skipped_names = {
        "delivery",
        "envio",
        "calificacion",
        "mundialistas",
        "mc para todos",
        "mctrios comida",
        "cajita feliz",
        "tu fav",
        "postres",
        "bebidas",
        "rappi",
    }
    for index, line in enumerate(lines):
        price = parse_money(line)
        if price is None:
            continue

        name = None
        for candidate in reversed(lines[max(0, index - 6) : index]):
            normalized = normalize_address_text(candidate)
            if normalized in skipped_names:
                continue
            if "resultados para" in normalized or "restaurantes" in normalized:
                continue
            if len(candidate) > 90 or candidate.startswith(("La ", "El ", "Disfruta ")):
                continue
            if parse_money(candidate) is not None:
                continue
            name = candidate
            break

        snippet = "\n".join(lines[max(0, index - 6) : index + 1])
        return name, price, snippet

    return None, None, ""


async def first_visible_with_money(locators: list[Locator], timeout_ms: int) -> Locator | None:
    for locator in locators:
        candidate = await first_visible([locator], timeout_ms=timeout_ms)
        if candidate is None:
            continue
        text = await safe_text(candidate)
        if parse_money(text) is not None:
            return candidate
    return None


async def click_suggestion(locator: Locator) -> None:
    """Click Rappi modal rows/buttons that may be covered by Chakra portal children."""

    try:
        await locator.click(timeout=2500)
        return
    except Exception:
        pass

    try:
        await locator.click(timeout=2500, force=True)
        return
    except Exception:
        pass

    await locator.evaluate(
        """(element) => {
            const clickable = element.closest('button,[role="button"],a') || element;
            clickable.click();
        }"""
    )


def is_rappi_error_text(text: str) -> bool:
    return bool(re.search(r"errorPage\.500|500\.title|500\.description", text, re.I))
