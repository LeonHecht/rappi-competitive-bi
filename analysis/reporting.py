"""Markdown report generation for executive delivery."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path("data/processed")
FIGURES_DIR = Path("reports/figures")
REPORTS_DIR = Path("reports")


def generate_report_artifacts(
    processed_dir: Path = PROCESSED_DIR,
    figures_dir: Path = FIGURES_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Path]:
    """Generate executive report and presentation outline from processed outputs."""

    reports_dir.mkdir(parents=True, exist_ok=True)
    clean = read_optional_csv(processed_dir / "clean_scrape.csv")
    summary = read_optional_csv(processed_dir / "summary_by_platform_zone.csv")
    promo = read_optional_csv(processed_dir / "promo_frequency_by_platform.csv")
    availability = read_optional_csv(processed_dir / "availability_by_platform_zone.csv")
    competitiveness = read_optional_csv(processed_dir / "rappi_competitiveness_metrics.csv")

    executive_path = reports_dir / "executive_report.md"
    outline_path = reports_dir / "presentation_outline.md"
    executive_path.write_text(
        build_executive_report(clean, summary, promo, availability, competitiveness, figures_dir),
        encoding="utf-8",
    )
    outline_path.write_text(build_presentation_outline(clean), encoding="utf-8")
    return {"executive_report": executive_path, "presentation_outline": outline_path}


def build_executive_report(
    clean: pd.DataFrame,
    summary: pd.DataFrame,
    promo: pd.DataFrame,
    availability: pd.DataFrame,
    competitiveness: pd.DataFrame,
    figures_dir: Path,
) -> str:
    rows = len(clean)
    platforms = safe_join(clean.get("platform"))
    addresses = safe_join(clean.get("address_id"))
    products = safe_join(clean.get("product_id"))
    zone_types = safe_join(clean.get("zone_type"))
    availability_rate = format_percent(clean["is_available"].mean()) if "is_available" in clean else "n/a"
    avg_total = format_money(clean["computed_final_total"].mean()) if "computed_final_total" in clean else "n/a"
    avg_fee = format_money(clean["delivery_fee"].mean()) if "delivery_fee" in clean else "n/a"
    avg_eta = format_minutes(clean["eta_midpoint"].mean()) if "eta_midpoint" in clean else "n/a"
    promo_rate = format_percent(clean["has_promo"].mean()) if "has_promo" in clean else "n/a"

    insights = build_insights(clean, competitiveness)

    return f"""# Executive Report: Competitive Intelligence Scraper

## Scope

This report summarizes the competitive intelligence dataset collected for Rappi, Uber Eats, and DiDi Food in Mexico. The system is designed to compare price, fees, delivery ETA, promotions, and availability across configured products and representative addresses.

## Methodology

The system uses Playwright browser automation with one adapter per platform. Raw observations are normalized into a shared schema, written as CSV/JSON, processed with pandas, and visualized through generated charts and a Streamlit dashboard.

The analysis pipeline computes:

- summary tables by platform and zone type
- price competitiveness index: `rappi_final_total / competitor_average_final_total`
- delivery fee gap: `rappi_delivery_fee - competitor_average_delivery_fee`
- ETA midpoint and ETA gap
- promo frequency by platform
- availability rate by platform and zone type

## Data Coverage

| Metric | Value |
|---|---:|
| Rows | {rows} |
| Platforms | {platforms} |
| Addresses | {addresses} |
| Zone types | {zone_types} |
| Products | {products} |
| Availability rate | {availability_rate} |
| Average final total | {avg_total} |
| Average delivery fee | {avg_fee} |
| Average ETA midpoint | {avg_eta} |
| Promo frequency | {promo_rate} |

## Scraping Limitations

- Public web flows differ by platform and can change without notice.
- Checkout-level service fees and final totals may require cart state or login.
- Rappi currently uses the address already selected in the persistent browser profile.
- DiDi Food may expose store-card data even when menu/product data is limited by availability or login state.
- Partial rows are preserved as `partial_success` or `failed` instead of being silently dropped.

## Top 5 Actionable Insights

{insights}

## Charts

### Average Final Total by Platform

![Average final total by platform]({figures_dir / "average_final_total_by_platform.png"})

### Delivery Fee by Platform and Zone Type

![Delivery fee by platform and zone type]({figures_dir / "delivery_fee_by_platform_zone_type.png"})

### ETA Heatmap by Address and Platform

![ETA heatmap by address and platform]({figures_dir / "eta_heatmap_by_address_platform.png"})

### Promo Frequency by Platform

![Promo frequency by platform]({figures_dir / "promo_frequency_by_platform.png"})

## Technical Architecture

1. Configuration: `config/addresses.yaml`, `config/products.yaml`, and `config/settings.yaml`.
2. Scraping: Playwright adapters under `scrapers/`, sharing `BaseScraper` and `ScrapeResult`.
3. Persistence: raw CSV/JSON outputs in `data/raw/` and screenshots in `reports/screenshots/`.
4. Analysis: `analysis/processing.py` cleans data, computes metrics, and generates chart files.
5. Delivery: `dashboard/app.py` exposes filters, metrics, visualizations, and report downloads.

## Ethical Considerations

- Collect only public or legitimately session-visible data.
- Avoid bypassing authentication, private APIs, or access controls.
- Keep request volume conservative and use the tool for analysis, not service disruption.
- Do not collect personal data.
- Clearly document missing or unavailable fields instead of inferring hidden data.

## Next Steps

1. Expand collection to 20-50 representative addresses.
2. Add more standardized products such as Big Mac, combo, nuggets, Coca-Cola, and water.
3. Collect balanced observations for Rappi, Uber Eats, and DiDi Food into `data/raw/scrape.csv`.
4. Add scheduled collection windows to analyze time-of-day variation.
5. Harden selectors and add parsing tests for each platform.
6. Convert this Markdown report to PDF for final submission if required.
"""


def build_presentation_outline(clean: pd.DataFrame) -> str:
    rows = len(clean)
    platforms = safe_join(clean.get("platform"))
    return f"""# 20-Minute Presentation Outline

## 1. Approach and Scope (3 min)

- Goal: automate competitive intelligence for Rappi versus Uber Eats and DiDi Food.
- Scope: standardized products, configured addresses, visible web marketplace metrics.
- Current processed dataset: {rows} rows across {platforms}.

## 2. Demo (3 min)

- Run one scraper command.
- Show raw CSV/JSON output.
- Show screenshots as evidence.
- Run analysis pipeline.
- Open Streamlit dashboard and report download.

## 3. Data Overview (3 min)

- Explain platforms, products, addresses, and zone types.
- Show availability, ETA, delivery fee, and promo coverage.
- Explain partial-success handling.

## 4. Top 5 Insights (5 min)

- Present the five finding / impact / recommendation blocks from the executive report.
- Anchor each insight in a table or chart.

## 5. Technical Decisions (3 min)

- Playwright for browser automation.
- Modular platform adapters.
- Persistent sessions for login/address-sensitive sites.
- Structured logging, retries, screenshots, CSV/JSON output.
- pandas + matplotlib/Streamlit for analysis and delivery.

## 6. Limitations and Next Steps (2 min)

- Checkout fees often require cart/login state.
- Selectors require maintenance.
- Need broader geographic and competitor coverage.
- Next: scheduled collection, parser tests, PDF export, more products.

## 7. Q&A Prep (1 min)

- Why scraping instead of APIs?
- How are failures handled?
- How would this scale?
- What are the ethical/legal boundaries?
- What would be productionized next?
"""


def build_insights(clean: pd.DataFrame, competitiveness: pd.DataFrame) -> str:
    available_rate = clean["is_available"].mean() if "is_available" in clean and not clean.empty else None
    promo_rate = clean["has_promo"].mean() if "has_promo" in clean and not clean.empty else None
    avg_fee = clean["delivery_fee"].mean() if "delivery_fee" in clean and not clean.empty else None
    avg_eta = clean["eta_midpoint"].mean() if "eta_midpoint" in clean and not clean.empty else None
    has_competitors = (
        "competitor_average_final_total" in competitiveness
        and competitiveness["competitor_average_final_total"].notna().any()
    )

    competitor_text = (
        "Rappi competitiveness metrics are populated for rows with competitor observations."
        if has_competitors
        else "Rappi competitiveness metrics are not yet populated because competitor observations are missing or incomplete."
    )

    return f"""### 1. Availability Is a Core Operational KPI

**Finding:** Current availability rate is {format_percent(available_rate)}.

**Impact:** Users cannot convert when stores or products are unavailable, regardless of price competitiveness.

**Recommendation:** Track availability by platform, zone type, product, and daypart before making pricing decisions.

### 2. Delivery Fee Is Directly Visible and Actionable

**Finding:** Average visible delivery fee is {format_money(avg_fee)}.

**Impact:** Delivery fee is one of the easiest user-visible levers to compare across platforms.

**Recommendation:** Use delivery fee gap by zone to identify where Rappi should subsidize or reposition delivery pricing.

### 3. ETA Can Be Compared Even When Checkout Fees Are Missing

**Finding:** Average ETA midpoint is {format_minutes(avg_eta)}.

**Impact:** ETA is available earlier in the funnel than checkout total and reflects operational competitiveness.

**Recommendation:** Prioritize ETA heatmaps by address and platform for Operations and marketplace balancing teams.

### 4. Promotions Need Separate Tracking from Base Price

**Finding:** Promo frequency is {format_percent(promo_rate)}.

**Impact:** Promotions can make a platform look cheaper without changing underlying menu prices.

**Recommendation:** Separate base price, delivery fee, and promo visibility in executive reporting.

### 5. Balanced Competitor Coverage Is Required for Final Pricing Conclusions

**Finding:** {competitor_text}

**Impact:** The system can compute the index, but the business conclusion depends on balanced Rappi, Uber Eats, and DiDi Food observations.

**Recommendation:** Run the canonical multi-platform scrape into `data/raw/scrape.csv` before presenting final pricing position claims.
"""


def read_optional_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def safe_join(series: pd.Series | None) -> str:
    if series is None:
        return "n/a"
    values = sorted(str(value) for value in series.dropna().unique())
    return ", ".join(values) if values else "n/a"


def format_money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"MX${value:,.2f}"


def format_minutes(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.0f} min"


def format_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.1%}"

