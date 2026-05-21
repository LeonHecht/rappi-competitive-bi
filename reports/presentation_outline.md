# 20-Minute Presentation Outline

## 1. Approach and Scope (3 min)

- Goal: automate competitive intelligence for Rappi versus Uber Eats and DiDi Food.
- Scope: standardized products, configured addresses, visible web marketplace metrics.
- Current processed dataset: 3 rows across rappi.

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
