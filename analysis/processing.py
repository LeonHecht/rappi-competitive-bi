"""Data loading, cleaning, and chart generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px


def load_raw_csv(path: Path) -> pd.DataFrame:
    """Load raw scraper output."""

    return pd.read_csv(path)


def normalize_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare price fields for comparison charts."""

    cleaned = df.copy()
    for column in ["price", "delivery_fee", "service_fee"]:
        if column in cleaned:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    return cleaned


def build_price_comparison_chart(df: pd.DataFrame):
    """Create a platform price comparison chart."""

    if df.empty or "platform" not in df or "price" not in df:
        return None
    return px.box(df, x="platform", y="price", color="platform", points="all")

