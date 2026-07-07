# Changelog
## v0.1.0 — 2026-07-06

Project scaffold: folder structure, config system, centralized logging, dependencies.
## v0.2.0 — 2026-07-07

Scraper (`scripts/scraper.py`) — Himalayas.app schema.org JobPosting
extraction, resumable/incremental, retry with backoff. 473 postings collected.
## v0.3.0 — 2026-07-07

Cleaning pipeline (`scripts/clean.py`) — dedup, currency/period-normalized
salary (live FX), long-format country/skill tables.
