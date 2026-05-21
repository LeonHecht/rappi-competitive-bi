"""Output writers for raw and processed data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_FIELDNAMES = [
    "address_id",
    "currency",
    "delivery_fee",
    "estimated_delivery_minutes",
    "item_name",
    "platform",
    "price",
    "product_id",
    "product_name",
    "rating",
    "raw_payload",
    "scraped_at",
    "service_fee",
    "store_name",
]


def resolve_output_paths(
    output: str | None,
    output_settings: dict[str, Any],
) -> tuple[Path, Path]:
    """Resolve CSV and JSON output paths from CLI/config."""

    if output is None:
        return (
            Path(output_settings.get("latest_csv", "data/raw/latest.csv")),
            Path(output_settings.get("latest_json", "data/raw/latest.json")),
        )

    output_path = Path(output)
    if output_path.suffix.lower() == ".csv":
        return output_path, output_path.with_suffix(".json")
    if output_path.suffix.lower() == ".json":
        return output_path.with_suffix(".csv"), output_path
    return output_path / "latest.csv", output_path / "latest.json"


def write_raw_outputs(rows: list[dict[str, Any]], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = sorted({key for row in rows for key in row}) if rows else DEFAULT_FIELDNAMES
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_serialize_csv_row(row) for row in rows)

    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(rows, json_file, ensure_ascii=False, indent=2, default=str)


def _serialize_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    serialized = row.copy()
    for key, value in serialized.items():
        if isinstance(value, (dict, list)):
            serialized[key] = json.dumps(value, ensure_ascii=False, default=str)
    return serialized
