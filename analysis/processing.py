"""Competitive intelligence data cleaning, metrics, and charts."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import yaml

RAW_INPUT_PATH = Path("data/raw/scrape.csv")
PROCESSED_DIR = Path("data/processed")
FIGURES_DIR = Path("reports/figures")
ADDRESS_CONFIG_PATH = Path("config/addresses.yaml")

MONEY_RE = re.compile(r"([0-9]+(?:[.,][0-9]{1,2})?)")
PROMO_KEYWORDS = re.compile("promo|promoci[oó]n|descuento|gratis|2x1|ahorra|offer|deal", re.I)


def run_analysis_pipeline(
    raw_path: Path = RAW_INPUT_PATH,
    processed_dir: Path = PROCESSED_DIR,
    figures_dir: Path = FIGURES_DIR,
) -> dict[str, Path]:
    """Run the full analysis pipeline and write processed artifacts."""

    processed_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    raw = load_raw_csv(raw_path)
    clean = clean_scrape(raw)
    clean = attach_zone_type(clean)
    clean = add_competitiveness_metrics(clean)

    outputs: dict[str, Path] = {}
    outputs["clean_scrape"] = processed_dir / "clean_scrape.csv"
    clean.to_csv(outputs["clean_scrape"], index=False)

    summary_tables = build_summary_tables(clean)
    for name, table in summary_tables.items():
        path = processed_dir / f"{name}.csv"
        table.to_csv(path, index=False)
        outputs[name] = path

    chart_paths = generate_charts(clean, figures_dir)
    outputs.update(chart_paths)
    return outputs


def load_raw_csv(path: Path) -> pd.DataFrame:
    """Load raw scraper output."""

    if not path.exists():
        raise FileNotFoundError(f"Raw scrape input not found: {path}")
    return pd.read_csv(path)


def clean_scrape(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize scraper output into analysis-ready columns."""

    clean = df.copy()
    ensure_columns(
        clean,
        {
            "platform": None,
            "address_id": None,
            "product_id": None,
            "product_name": None,
            "zone_type": None,
            "price": None,
            "delivery_fee": None,
            "service_fee": None,
            "final_total": None,
            "estimated_delivery_minutes": None,
            "visible_promotions": None,
            "status": None,
            "error": None,
        },
    )

    clean["platform"] = clean["platform"].astype("string").str.strip()
    clean["address_id"] = clean["address_id"].astype("string").str.strip()
    clean["product_id"] = clean["product_id"].astype("string").str.strip()
    clean["product_name"] = clean["product_name"].astype("string").str.strip()
    clean["zone_type"] = clean["zone_type"].astype("string").str.strip()

    for column in ["price", "delivery_fee", "service_fee", "final_total", "estimated_delivery_minutes"]:
        clean[column] = clean[column].map(parse_numeric_value)

    clean["eta_midpoint"] = clean["estimated_delivery_minutes"]
    clean["promo_count"] = clean["visible_promotions"].map(count_promotions)
    clean["has_promo"] = clean["promo_count"] > 0
    clean["is_available"] = clean.apply(infer_availability, axis=1)

    clean["computed_final_total"] = clean["final_total"]
    fallback_total = clean["price"].notna()
    clean.loc[fallback_total & clean["computed_final_total"].isna(), "computed_final_total"] = (
        clean.loc[fallback_total, "price"].fillna(0)
        + clean.loc[fallback_total, "delivery_fee"].fillna(0)
        + clean.loc[fallback_total, "service_fee"].fillna(0)
    )
    clean["final_total_source"] = "reported"
    clean.loc[clean["final_total"].isna() & clean["computed_final_total"].notna(), "final_total_source"] = (
        "computed_from_visible_components"
    )
    clean.loc[clean["computed_final_total"].isna(), "final_total_source"] = "missing"
    return clean


def attach_zone_type(df: pd.DataFrame, config_path: Path = ADDRESS_CONFIG_PATH) -> pd.DataFrame:
    """Attach zone type from config when raw data does not include it."""

    clean = df.copy()
    zone_map = load_address_zone_map(config_path)
    missing_zone = clean["zone_type"].isna() | (clean["zone_type"].astype("string").str.len() == 0)
    clean.loc[missing_zone, "zone_type"] = clean.loc[missing_zone, "address_id"].map(zone_map)
    clean["zone_type"] = clean["zone_type"].fillna("unknown")
    return clean


def add_competitiveness_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add Rappi-vs-competitor total, delivery, and ETA gap metrics."""

    clean = df.copy()
    keys = ["address_id", "product_id"]
    competitor_mask = clean["platform"].str.lower() != "rappi"
    competitor_avg = (
        clean.loc[competitor_mask]
        .groupby(keys, dropna=False)
        .agg(
            competitor_average_final_total=("computed_final_total", "mean"),
            competitor_average_delivery_fee=("delivery_fee", "mean"),
            competitor_average_eta_midpoint=("eta_midpoint", "mean"),
        )
        .reset_index()
    )
    clean = clean.merge(competitor_avg, on=keys, how="left")

    rappi_mask = clean["platform"].str.lower() == "rappi"
    clean["price_competitiveness_index"] = pd.NA
    clean.loc[rappi_mask, "price_competitiveness_index"] = (
        clean.loc[rappi_mask, "computed_final_total"]
        / clean.loc[rappi_mask, "competitor_average_final_total"]
    )
    clean["delivery_fee_gap"] = pd.NA
    clean.loc[rappi_mask, "delivery_fee_gap"] = (
        clean.loc[rappi_mask, "delivery_fee"]
        - clean.loc[rappi_mask, "competitor_average_delivery_fee"]
    )
    clean["eta_gap"] = pd.NA
    clean.loc[rappi_mask, "eta_gap"] = (
        clean.loc[rappi_mask, "eta_midpoint"]
        - clean.loc[rappi_mask, "competitor_average_eta_midpoint"]
    )
    return clean


def build_summary_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build required summary tables."""

    by_platform_zone = (
        df.groupby(["platform", "zone_type"], dropna=False)
        .agg(
            rows=("platform", "size"),
            availability_rate=("is_available", "mean"),
            average_price=("price", "mean"),
            average_final_total=("computed_final_total", "mean"),
            average_delivery_fee=("delivery_fee", "mean"),
            average_eta_midpoint=("eta_midpoint", "mean"),
            promo_frequency=("has_promo", "mean"),
        )
        .reset_index()
    )

    competitiveness = df.loc[df["platform"].str.lower() == "rappi", [
        "address_id",
        "product_id",
        "product_name",
        "zone_type",
        "computed_final_total",
        "competitor_average_final_total",
        "price_competitiveness_index",
        "delivery_fee",
        "competitor_average_delivery_fee",
        "delivery_fee_gap",
        "eta_midpoint",
        "competitor_average_eta_midpoint",
        "eta_gap",
    ]].copy()

    promo_frequency = (
        df.groupby("platform", dropna=False)
        .agg(rows=("platform", "size"), promo_rows=("has_promo", "sum"), promo_frequency=("has_promo", "mean"))
        .reset_index()
    )

    availability = (
        df.groupby(["platform", "zone_type"], dropna=False)
        .agg(rows=("platform", "size"), available_rows=("is_available", "sum"), availability_rate=("is_available", "mean"))
        .reset_index()
    )

    return {
        "summary_by_platform_zone": by_platform_zone,
        "rappi_competitiveness_metrics": competitiveness,
        "promo_frequency_by_platform": promo_frequency,
        "availability_by_platform_zone": availability,
    }


def generate_charts(df: pd.DataFrame, figures_dir: Path = FIGURES_DIR) -> dict[str, Path]:
    """Generate required chart PNG files."""

    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}

    outputs["chart_average_final_total"] = figures_dir / "average_final_total_by_platform.png"
    plot_bar(
        df.groupby("platform", dropna=False)["computed_final_total"].mean().dropna(),
        "Average Final Total by Platform",
        "Platform",
        "MXN",
        outputs["chart_average_final_total"],
    )

    outputs["chart_delivery_fee_zone"] = figures_dir / "delivery_fee_by_platform_zone_type.png"
    delivery = df.pivot_table(
        index="platform",
        columns="zone_type",
        values="delivery_fee",
        aggfunc="mean",
    )
    plot_grouped_bar(delivery, "Delivery Fee by Platform and Zone Type", "Platform", "MXN", outputs["chart_delivery_fee_zone"])

    outputs["chart_eta_heatmap"] = figures_dir / "eta_heatmap_by_address_platform.png"
    eta = df.pivot_table(index="address_id", columns="platform", values="eta_midpoint", aggfunc="mean")
    plot_heatmap(eta, "ETA Midpoint Heatmap by Address and Platform", outputs["chart_eta_heatmap"])

    outputs["chart_promo_frequency"] = figures_dir / "promo_frequency_by_platform.png"
    promo = df.groupby("platform", dropna=False)["has_promo"].mean().dropna()
    plot_bar(promo, "Promo Frequency by Platform", "Platform", "Share of Rows", outputs["chart_promo_frequency"])

    return outputs


def normalize_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible helper for dashboards."""

    return clean_scrape(df)


def build_price_comparison_chart(df: pd.DataFrame):
    """Backward-compatible Plotly chart helper."""

    import plotly.express as px

    clean = normalize_prices(df)
    if clean.empty or "platform" not in clean or "price" not in clean:
        return None
    return px.box(clean, x="platform", y="price", color="platform", points="all")


def ensure_columns(df: pd.DataFrame, defaults: dict[str, Any]) -> None:
    for column, default in defaults.items():
        if column not in df:
            df[column] = default


def parse_numeric_value(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if re.search("gratis|free|sin costo", text, re.I):
        return 0.0
    match = MONEY_RE.search(text.replace(",", "."))
    return float(match.group(1)) if match else None


def count_promotions(value: Any) -> int:
    parsed = parse_list_like(value)
    if parsed:
        return len([item for item in parsed if str(item).strip()])
    text = "" if value is None or pd.isna(value) else str(value)
    return 1 if PROMO_KEYWORDS.search(text) else 0


def parse_list_like(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def infer_availability(row: pd.Series) -> bool:
    status = str(row.get("status", "")).lower()
    error = row.get("error")
    if status == "failed" or (isinstance(error, str) and error.strip()):
        return False
    if pd.notna(row.get("price")) or pd.notna(row.get("delivery_fee")) or pd.notna(row.get("eta_midpoint")):
        return True
    if status in {"success", "partial_success"}:
        return True
    return False


def load_address_zone_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return {
        item["id"]: item.get("zone_type", "unknown")
        for item in data.get("addresses", [])
        if "id" in item
    }


def plot_bar(series: pd.Series, title: str, xlabel: str, ylabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    if series.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
    else:
        series.plot(kind="bar", ax=ax, color="#ff6b35")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_grouped_bar(table: pd.DataFrame, title: str, xlabel: str, ylabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    if table.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
    else:
        table.plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_heatmap(table: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    if table.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
    else:
        image = ax.imshow(table.fillna(0).to_numpy(), cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(len(table.columns)), labels=table.columns, rotation=30, ha="right")
        ax.set_yticks(range(len(table.index)), labels=table.index)
        for row_idx, row_label in enumerate(table.index):
            for col_idx, col_label in enumerate(table.columns):
                value = table.loc[row_label, col_label]
                label = "" if pd.isna(value) else f"{value:.0f}"
                ax.text(col_idx, row_idx, label, ha="center", va="center", color="black")
        fig.colorbar(image, ax=ax, label="Minutes")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)

