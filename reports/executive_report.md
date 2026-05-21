# Executive Report: Competitive Intelligence Scraper

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
| Rows | 3 |
| Platforms | rappi |
| Addresses | cdmx_condesa |
| Zone types | dense_urban |
| Products | burger, coffee, sushi |
| Availability rate | 66.7% |
| Average final total | MX$122.00 |
| Average delivery fee | MX$0.00 |
| Average ETA midpoint | 19 min |
| Promo frequency | 66.7% |

## Scraping Limitations

- Public web flows differ by platform and can change without notice.
- Checkout-level service fees and final totals may require cart state or login.
- Rappi currently uses the address already selected in the persistent browser profile.
- DiDi Food may expose store-card data even when menu/product data is limited by availability or login state.
- Partial rows are preserved as `partial_success` or `failed` instead of being silently dropped.

## Top 5 Actionable Insights

### 1. Availability Is a Core Operational KPI

**Finding:** Current availability rate is 66.7%.

**Impact:** Users cannot convert when stores or products are unavailable, regardless of price competitiveness.

**Recommendation:** Track availability by platform, zone type, product, and daypart before making pricing decisions.

### 2. Delivery Fee Is Directly Visible and Actionable

**Finding:** Average visible delivery fee is MX$0.00.

**Impact:** Delivery fee is one of the easiest user-visible levers to compare across platforms.

**Recommendation:** Use delivery fee gap by zone to identify where Rappi should subsidize or reposition delivery pricing.

### 3. ETA Can Be Compared Even When Checkout Fees Are Missing

**Finding:** Average ETA midpoint is 19 min.

**Impact:** ETA is available earlier in the funnel than checkout total and reflects operational competitiveness.

**Recommendation:** Prioritize ETA heatmaps by address and platform for Operations and marketplace balancing teams.

### 4. Promotions Need Separate Tracking from Base Price

**Finding:** Promo frequency is 66.7%.

**Impact:** Promotions can make a platform look cheaper without changing underlying menu prices.

**Recommendation:** Separate base price, delivery fee, and promo visibility in executive reporting.

### 5. Balanced Competitor Coverage Is Required for Final Pricing Conclusions

**Finding:** Rappi competitiveness metrics are not yet populated because competitor observations are missing or incomplete.

**Impact:** The system can compute the index, but the business conclusion depends on balanced Rappi, Uber Eats, and DiDi Food observations.

**Recommendation:** Run the canonical multi-platform scrape into `data/raw/scrape.csv` before presenting final pricing position claims.


## Charts

### Average Final Total by Platform

![Average final total by platform](reports/figures/average_final_total_by_platform.png)

### Delivery Fee by Platform and Zone Type

![Delivery fee by platform and zone type](reports/figures/delivery_fee_by_platform_zone_type.png)

### ETA Heatmap by Address and Platform

![ETA heatmap by address and platform](reports/figures/eta_heatmap_by_address_platform.png)

### Promo Frequency by Platform

![Promo frequency by platform](reports/figures/promo_frequency_by_platform.png)

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
