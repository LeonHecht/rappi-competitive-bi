"""CLI entry point for collecting competitive intelligence data."""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, TypeVar

from config_loader import load_addresses, load_products, load_settings
from logging_config import configure_logging
from output import resolve_output_paths, write_raw_outputs
from scrapers.base import Address, ProductQuery, ScrapeResult
from scrapers.registry import SCRAPER_REGISTRY

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


def parse_csv_arg(value: str | None) -> list[str] | None:
    """Parse comma-separated CLI filters."""

    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def filter_by_id(items: Iterable[T], selected_ids: list[str] | None) -> list[T]:
    """Filter dataclass-like config objects by their `id` attribute."""

    item_list = list(items)
    if not selected_ids:
        return item_list
    selected = set(selected_ids)
    filtered = [item for item in item_list if getattr(item, "id") in selected]
    missing = selected - {getattr(item, "id") for item in filtered}
    if missing:
        LOGGER.warning("Unknown config ids skipped", extra={"ids": sorted(missing)})
    return filtered


def limit_combinations(
    platforms: list[str],
    addresses: list[Address],
    products: list[ProductQuery],
    limit: int | None,
) -> list[tuple[str, Address, ProductQuery]]:
    combinations = [
        (platform, address, product)
        for platform in platforms
        for address in addresses
        for product in products
    ]
    if limit is None:
        return combinations
    return combinations[: max(limit, 0)]


def build_mock_results(
    combinations: list[tuple[str, Address, ProductQuery]],
) -> list[ScrapeResult]:
    now = datetime.now(UTC).isoformat()
    results: list[ScrapeResult] = []
    for index, (platform, address, product) in enumerate(combinations, start=1):
        results.append(
            ScrapeResult(
                platform=platform,
                address_id=address.id,
                product_id=product.id,
                product_name=product.name,
                store_name=f"Mock Store {index}",
                item_name=f"Mock {product.name}",
                price=99.0 + index,
                currency="MXN",
                delivery_fee=15.0,
                service_fee=5.0,
                estimated_delivery_minutes=30,
                rating=4.5,
                raw_payload={
                    "mode": "dry_run",
                    "address_label": address.label,
                    "product_category": product.category,
                },
                scraped_at=now,
            )
        )
    return results


async def run_scrapers(args: argparse.Namespace) -> None:
    settings = load_settings()
    addresses = filter_by_id(load_addresses(), parse_csv_arg(args.addresses))
    products = filter_by_id(load_products(), parse_csv_arg(args.products))

    scraping_settings = settings.get("scraping", {})
    output_settings = settings.get("output", {})
    platforms = args.platform or scraping_settings.get("platforms", list(SCRAPER_REGISTRY))
    combinations = limit_combinations(platforms, addresses, products, args.limit)
    csv_path, json_path = resolve_output_paths(args.output, output_settings)

    if args.dry_run:
        LOGGER.info("Running dry-run without browser", extra={"combination_count": len(combinations)})
        rows = [result.to_dict() for result in build_mock_results(combinations)]
        write_raw_outputs(rows, csv_path, json_path)
        LOGGER.info("Dry-run completed", extra={"row_count": len(rows)})
        return

    headless = bool(scraping_settings.get("headless", True)) if args.headless is None else args.headless
    timeout_ms = int(scraping_settings.get("timeout_ms", 30000))
    screenshots_dir = Path(scraping_settings.get("screenshots_dir", "reports/screenshots"))
    user_data_dir = args.user_data_dir or scraping_settings.get("user_data_dir")
    rows: list[dict] = []

    from scrapers.session import browser_session

    async with browser_session(
        headless=headless,
        timeout_ms=timeout_ms,
        user_data_dir=Path(user_data_dir) if user_data_dir else None,
    ) as context:
        for platform, address, product in combinations:
            scraper_cls = SCRAPER_REGISTRY.get(platform)
            if scraper_cls is None:
                LOGGER.warning("Unknown platform skipped", extra={"platform": platform})
                continue

            scraper = scraper_cls(context=context, screenshot_dir=screenshots_dir)
            LOGGER.info(
                "Starting scrape",
                extra={
                    "platform": platform,
                    "address_id": address.id,
                    "product_id": product.id,
                },
            )
            try:
                results = await scraper.scrape(address, product)
            except NotImplementedError as exc:
                LOGGER.info(
                    "Scraper placeholder reached",
                    extra={"platform": platform, "error": str(exc)},
                )
                continue
            rows.extend(result.to_dict() for result in results)

    write_raw_outputs(rows, csv_path, json_path)
    LOGGER.info("Scrape run completed", extra={"row_count": len(rows)})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competitive intelligence scraper")
    parser.add_argument(
        "--platform",
        action="append",
        choices=sorted(SCRAPER_REGISTRY),
        help="Platform to run. Can be passed multiple times.",
    )
    parser.add_argument(
        "--addresses",
        help="Comma-separated address IDs from config/addresses.yaml.",
    )
    parser.add_argument(
        "--products",
        help="Comma-separated product IDs from config/products.yaml.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of platform/address/product combinations to run.",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run Chromium in headless mode. Use --no-headless for visible browser.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory or CSV path. JSON is written next to the CSV.",
    )
    parser.add_argument(
        "--user-data-dir",
        default=None,
        help="Persistent Chromium profile directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write mock results from config without opening a browser.",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    asyncio.run(run_scrapers(args))


if __name__ == "__main__":
    main()
