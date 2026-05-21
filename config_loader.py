"""Configuration loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scrapers.base import Address, ProductQuery


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_addresses(path: Path = Path("config/addresses.yaml")) -> list[Address]:
    data = load_yaml(path)
    return [Address(**item) for item in data.get("addresses", [])]


def load_products(path: Path = Path("config/products.yaml")) -> list[ProductQuery]:
    data = load_yaml(path)
    return [ProductQuery(**item) for item in data.get("products", [])]


def load_settings(path: Path = Path("config/settings.yaml")) -> dict[str, Any]:
    return load_yaml(path)

