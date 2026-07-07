# Job Market Intelligence Dashboard

A data engineering + BI portfolio project: scrapes Data Analyst job postings
from Himalayas.app, cleans and normalizes them into a SQLite database, and
surfaces business-facing insights (skill demand, salary, geography, hiring
trends) through a Plotly notebook dashboard and a Power BI report.

**Status:** Stage 1 (project scaffold) complete. Full documentation —
architecture diagram, data dictionary, ETL walkthrough, installation guide —
lands in a later stage once the pipeline is built end to end.

## Structure

```
JobMarketAnalysis/
├── .github/workflows/   CI + scheduled scraper runs
├── assets/              Chart exports, screenshots
├── config/
│   └── config.yaml      All tunable settings (scraper, paths, skills, logging)
├── dashboard/            Plotly / Power BI outputs
├── data/
│   ├── raw/              Raw scrapes (git-ignored)
│   └── cleaned/           Cleaned CSVs (committed)
├── database/             SQLite database (committed)
├── docs/                 Architecture diagram, data dictionary
├── logs/                 Rotating log files (git-ignored)
├── notebooks/            EDA (Plotly)
├── scripts/
│   ├── config.py         Config loader
│   └── logger.py         Centralized logging
├── tests/
├── requirements.txt
├── LICENSE
└── CHANGELOG.md
```

## Data Source

[Himalayas.app](https://himalayas.app) — permissive robots.txt (`Allow: /`)
with dedicated job/skill/salary sitemaps. Scraped politely: rate-limited
requests, identifying user agent, retry with backoff (see `config/config.yaml`).

## How to Run

```bash
pip install -r requirements.txt
```

(Scraper, cleaning, database, and analysis commands land as each stage is built.)

## Author

Gabriel Alegre Caña
