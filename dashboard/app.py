"""Streamlit dashboard for competitive intelligence outputs."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis.processing import add_competitiveness_metrics, attach_zone_type, clean_scrape
from analysis.reporting import generate_report_artifacts

PROCESSED_DATA_PATH = Path("data/processed/clean_scrape.csv")
RAW_DATA_PATH = Path("data/raw/scrape.csv")
EXECUTIVE_REPORT_PATH = Path("reports/executive_report.md")
PRESENTATION_OUTLINE_PATH = Path("reports/presentation_outline.md")


def main() -> None:
    st.set_page_config(page_title="Rappi Competitive BI", layout="wide")
    st.title("Competitive Intelligence Dashboard")

    df = load_dashboard_data()
    if df.empty:
        st.info("No data found. Run `python -m analysis.run_pipeline --input data/raw/scrape.csv` first.")
        return

    filtered = apply_filters(df)
    render_metrics(filtered)
    render_charts(filtered)
    render_report_downloads()

    st.subheader("Clean Data")
    st.dataframe(filtered, use_container_width=True)


def load_dashboard_data() -> pd.DataFrame:
    uploaded = st.sidebar.file_uploader("Load CSV", type=["csv"])
    if uploaded is not None:
        raw = pd.read_csv(uploaded)
        return add_competitiveness_metrics(attach_zone_type(clean_scrape(raw)))
    if PROCESSED_DATA_PATH.exists():
        return pd.read_csv(PROCESSED_DATA_PATH)
    if RAW_DATA_PATH.exists():
        return add_competitiveness_metrics(attach_zone_type(clean_scrape(pd.read_csv(RAW_DATA_PATH))))
    return pd.DataFrame()


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    filtered = df.copy()

    for column, label in [
        ("platform", "Platform"),
        ("zone_type", "Zone Type"),
        ("product_id", "Product"),
        ("address_id", "Address"),
    ]:
        if column not in filtered:
            continue
        values = sorted(value for value in filtered[column].dropna().unique())
        selected = st.sidebar.multiselect(label, values, default=values)
        if selected:
            filtered = filtered[filtered[column].isin(selected)]

    return filtered


def render_metrics(df: pd.DataFrame) -> None:
    st.subheader("Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", f"{len(df):,}")
    col2.metric("Availability", format_percent(df["is_available"].mean()) if "is_available" in df else "n/a")
    col3.metric(
        "Avg Final Total",
        format_money(df["computed_final_total"].mean()) if "computed_final_total" in df else "n/a",
    )
    col4.metric("Promo Frequency", format_percent(df["has_promo"].mean()) if "has_promo" in df else "n/a")


def render_charts(df: pd.DataFrame) -> None:
    st.subheader("Charts")
    if df.empty:
        st.info("No rows match the selected filters.")
        return

    col1, col2 = st.columns(2)
    with col1:
        if "computed_final_total" in df:
            chart = px.bar(
                df.groupby("platform", as_index=False)["computed_final_total"].mean(),
                x="platform",
                y="computed_final_total",
                title="Average Final Total by Platform",
            )
            st.plotly_chart(chart, use_container_width=True)

    with col2:
        if {"platform", "zone_type", "delivery_fee"}.issubset(df.columns):
            chart = px.bar(
                df.groupby(["platform", "zone_type"], as_index=False)["delivery_fee"].mean(),
                x="platform",
                y="delivery_fee",
                color="zone_type",
                barmode="group",
                title="Delivery Fee by Platform and Zone Type",
            )
            st.plotly_chart(chart, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        if {"address_id", "platform", "eta_midpoint"}.issubset(df.columns):
            eta = df.pivot_table(index="address_id", columns="platform", values="eta_midpoint", aggfunc="mean")
            chart = px.imshow(
                eta,
                text_auto=".0f",
                aspect="auto",
                title="ETA Heatmap by Address and Platform",
                labels={"color": "Minutes"},
            )
            st.plotly_chart(chart, use_container_width=True)

    with col4:
        if {"platform", "has_promo"}.issubset(df.columns):
            chart = px.bar(
                df.groupby("platform", as_index=False)["has_promo"].mean(),
                x="platform",
                y="has_promo",
                title="Promo Frequency by Platform",
            )
            st.plotly_chart(chart, use_container_width=True)


def render_report_downloads() -> None:
    st.subheader("Executive Deliverables")
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("Generate executive report", type="primary"):
            outputs = generate_report_artifacts()
            st.success(
                "Generated: "
                + ", ".join(str(path) for path in outputs.values())
            )

    with col2:
        if EXECUTIVE_REPORT_PATH.exists():
            st.download_button(
                "Download report",
                EXECUTIVE_REPORT_PATH.read_text(encoding="utf-8"),
                file_name="executive_report.md",
                mime="text/markdown",
            )
        else:
            st.caption("Generate the report first.")

    with col3:
        if PRESENTATION_OUTLINE_PATH.exists():
            st.download_button(
                "Download presentation outline",
                PRESENTATION_OUTLINE_PATH.read_text(encoding="utf-8"),
                file_name="presentation_outline.md",
                mime="text/markdown",
            )


def format_money(value: float | None) -> str:
    if pd.isna(value):
        return "n/a"
    return f"MX${value:,.2f}"


def format_percent(value: float | None) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.1%}"


if __name__ == "__main__":
    main()
