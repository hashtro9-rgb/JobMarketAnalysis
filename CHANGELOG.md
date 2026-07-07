# Changelog
## v0.1.0 — 2026-07-06

Project scaffold: folder structure, config system, centralized logging, dependencies.
## v0.2.0 — 2026-07-07

Scraper (`scripts/scraper.py`) — Himalayas.app schema.org JobPosting
extraction, resumable/incremental, retry with backoff. 473 postings collected.
## v0.3.0 — 2026-07-07

Cleaning pipeline (`scripts/clean.py`) — dedup, currency/period-normalized
salary (live FX), long-format country/skill tables.
## v0.4.0 — 2026-07-07

Normalized SQLite database (`scripts/models.py`, `load_database.py`) —
Jobs/Companies/Skills/Locations + JobSkills/JobLocations junctions,
idempotent loader.
## v0.5.0 — 2026-07-07

EDA notebook (`notebooks/eda.ipynb`) — Plotly, executed end-to-end with real
outputs across pricing, sales, skills, geography, salary, and hiring-trend
analyses.
