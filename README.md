# Rappi Competitive BI

Python project for collecting and analyzing competitive intelligence across Rappi, Uber Eats, and DiDi Food in Mexico.

It includes a generic Playwright scraping framework, platform adapters, persistent Chromium profile support, structured logging, retry helpers, screenshot capture, CSV/JSON outputs, an analysis pipeline, generated charts, and a Streamlit dashboard.

## Project Structure

```text
scrapers/
analysis/
dashboard/
config/
data/raw/
data/processed/
reports/
main.py
requirements.txt
README.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m playwright install-deps chromium
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
python -m playwright install-deps chromium
```

## Configuration

Edit these files before running scrapes:

- `config/addresses.yaml`: delivery addresses to test.
- `config/products.yaml`: product searches to compare.
- `config/settings.yaml`: enabled platforms, browser mode, timeouts, screenshot path, and output paths.

## Run Scrapers

```bash
python main.py
```

Run a single platform:

```bash
python main.py --platform rappi
python main.py --platform uber_eats
python main.py --platform didi_food
```

Filter configured addresses and products by ID:

```bash
python main.py --addresses cdmx_condesa --products burger,coffee --limit 5
```

Use a visible browser or persistent browser profile:

```bash
python main.py --no-headless --user-data-dir .browser-profile
```

Write outputs to a custom directory or CSV path:

```bash
python main.py --output reports/run-001
python main.py --output data/raw/run-001.csv
```

Run without opening a browser:

```bash
python main.py --dry-run --output data/raw/dry-run.csv
```

### Recommended Collection Flow

Use `data/raw/scrape.csv` as the canonical raw file for analysis:

```bash
python main.py \
  --platform rappi \
  --platform uber_eats \
  --platform didi_food \
  --addresses cdmx_condesa \
  --products burger \
  --no-headless \
  --user-data-dir .browser-profile \
  --output data/raw/scrape.csv
```

For quick platform-specific tests:

```bash
python main.py --platform rappi --addresses cdmx_condesa --products burger --limit 1 --no-headless --user-data-dir .browser-profile --output data/raw/rappi-test.csv
python main.py --platform uber_eats --addresses cdmx_condesa --products burger --limit 1 --no-headless --user-data-dir .browser-profile --output data/raw/uber-live-test.csv
python main.py --platform didi_food --addresses cdmx_condesa --products burger --limit 1 --no-headless --user-data-dir .browser-profile --output data/raw/didi-test.csv
```

The platform adapters use best-effort public web selectors. If a platform needs session state, run with a persistent profile and complete setup manually:

```bash
python main.py --platform rappi --no-headless --user-data-dir .browser-profile --limit 1
python main.py --platform didi_food --no-headless --user-data-dir .browser-profile --limit 1
```

Checkout-level fields such as service fee and final total may be unavailable from the merchant menu page. In that case the scraper writes `partial_success` and lists missing fields in `raw_payload.missing_fields`.

Current platform notes:

- Uber Eats: supports web address setup, McDonald's merchant selection, product matching, menu price, ETA, promotions, and visible fees when exposed.
- Rappi: uses the address already selected in the persistent browser session. Set the desired address manually in `.browser-profile` before running.
- DiDi Food: uses the public `didi-food.com/es-MX/food/` page. It can collect store-card data such as ETA, delivery fee, rating, and promotions; menu-level product data may be unavailable depending on store availability/login state.

## Outputs

Raw outputs are written to:

- `data/raw/latest.csv`
- `data/raw/latest.json`

Screenshots are written to:

- `reports/screenshots/`

## Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard loads `data/processed/clean_scrape.csv` by default, or accepts an uploaded CSV.

## Analysis Pipeline

Use `data/raw/scrape.csv` as the canonical raw input:

```bash
python -m analysis.run_pipeline --input data/raw/scrape.csv
```

If you only have a platform test file, pass that file instead:

```bash
python -m analysis.run_pipeline --input data/raw/rappi-test.csv
```

The pipeline writes:

- `data/processed/clean_scrape.csv`
- `data/processed/summary_by_platform_zone.csv`
- `data/processed/rappi_competitiveness_metrics.csv`
- `data/processed/promo_frequency_by_platform.csv`
- `data/processed/availability_by_platform_zone.csv`
- chart PNGs in `reports/figures/`

Then launch the dashboard:

```bash
streamlit run dashboard/app.py
```

In the dashboard, use the **Executive Deliverables** section to:

- generate `reports/executive_report.md`
- download the executive report
- download the 20-minute presentation outline

Dashboard filters:

- platform
- zone_type
- product
- address

The analysis computes:

- summary tables by platform and zone type
- `price_competitiveness_index = rappi_final_total / competitor_average_final_total`
- `delivery_fee_gap = rappi_delivery_fee - competitor_average_delivery_fee`
- ETA midpoint and Rappi ETA gap
- promo frequency by platform
- availability rate by platform and zone type

## Selector Maintenance

Each adapter keeps platform-specific selectors in its own file under `scrapers/`. Prefer role, placeholder, and visible-text locators. If a live smoke test fails, inspect the saved screenshot and adjust only the affected platform adapter.
