# Rappi Competitive BI

Python project scaffold for a competitive intelligence scraper that compares Rappi, Uber Eats, and DiDi Food in Mexico.

This version defines a generic scraping framework with a `BaseScraper`, platform adapters, browser session initialization, optional persistent Chromium profile support, configuration files, structured logging, retry helpers, screenshot capture, raw CSV/JSON output, dry-run mode, and a Streamlit dashboard. Platform-specific selectors are intentionally left as TODOs.

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
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
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

Current adapters raise `NotImplementedError` after opening each platform homepage because selectors are not implemented yet.

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

The dashboard loads `data/raw/latest.csv` by default, or accepts an uploaded CSV.

## Next Implementation Step

For each platform adapter in `scrapers/`, implement:

- `set_address`
- `search_product`
- `extract_results`

Keep each adapter responsible for selectors and platform-specific behavior, and return normalized `ScrapeResult` records for downstream processing.
