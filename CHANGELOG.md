# Changelog

## v0.8.0 — 2026-07-07

GitHub Pages deployment (`.github/workflows/pages.yml`) publishing both HTML
dashboards as a live site, and a full README rewrite with live dashboard
links, complete architecture diagram, data dictionary, and per-stage run
instructions.

## v0.7.1 — 2026-07-07

Market analysis writeup (`docs/market_analysis.md`) — skill pay premiums,
experience-level compensation curve, geographic concentration, and data
quality findings (survivorship bias in the monthly trend from point-in-time
scraping, a currency-tagging outlier inflating one salary bucket, and a
dedup gap that misses same-employer reposts under different URLs).

## v0.7.0 — 2026-07-07

Executive dashboard (`dashboard/executive_dashboard.html`) — single self-contained
HTML file (Chart.js via CDN, no build step), rebuilt from the raw job postings
rather than pre-aggregated exports so cross-cutting filters (experience, work
setup, country) recompute every KPI and chart consistently. Adds an executive
summary panel with headline insights, and corrects country-demand figures to
count all countries a remote posting is eligible in (not just one "primary"
country per posting).

## v0.6.0 — 2026-07-07

Power BI data layer: 11 analytical SQL views (`database/views.sql`), a
star-schema CSV export with a generated Date dimension
(`dashboard/powerbi_data/`), and a full page-by-page report design spec
(`docs/powerbi_design_spec.md`).

## v0.5.0 — 2026-07-07

EDA notebook (`notebooks/eda.ipynb`) — Plotly, executed end-to-end with real
outputs across pricing, sales, skills, geography, salary, and hiring-trend
analyses.

## v0.4.0 — 2026-07-07

Normalized SQLite database (`scripts/models.py`, `load_database.py`) —
Jobs/Companies/Skills/Locations + JobSkills/JobLocations junctions,
idempotent loader.

## v0.3.0 — 2026-07-07

Cleaning pipeline (`scripts/clean.py`) — dedup, currency/period-normalized
salary (live FX), long-format country/skill tables.

## v0.2.0 — 2026-07-07

Scraper (`scripts/scraper.py`) — Himalayas.app schema.org JobPosting
extraction, resumable/incremental, retry with backoff. 473 postings collected.

## v0.1.0 — 2026-07-06

Project scaffold: folder structure, config system, centralized logging, dependencies.
