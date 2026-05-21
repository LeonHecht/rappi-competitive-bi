"""Streamlit dashboard for competitive intelligence outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from analysis.processing import build_price_comparison_chart, normalize_prices

RAW_DATA_PATH = Path("data/raw/latest.csv")


def main() -> None:
    st.set_page_config(page_title="Rappi Competitive BI", layout="wide")
    st.title("Competitive Intelligence Dashboard")

    uploaded = st.file_uploader("Load raw CSV", type=["csv"])
    if uploaded is not None:
        df = pd.read_csv(uploaded)
    elif RAW_DATA_PATH.exists():
        df = pd.read_csv(RAW_DATA_PATH)
    else:
        st.info("No scraper output found yet. Run `python main.py` or upload a CSV.")
        return

    df = normalize_prices(df)
    st.dataframe(df, use_container_width=True)

    chart = build_price_comparison_chart(df)
    if chart is not None:
        st.plotly_chart(chart, use_container_width=True)


if __name__ == "__main__":
    main()

