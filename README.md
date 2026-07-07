# Job Market Intelligence Dashboard

A full, working data engineering + BI pipeline: it scrapes live Data Analyst
job postings, cleans and normalizes them into a relational database, and
surfaces the results through three separate analytical surfaces — a Jupyter
EDA notebook, two self-contained HTML dashboards, and a Power BI report spec
— plus a written market analysis with explicit data-quality findings.

**Status:** all 7 build stages complete (v0.1.0 → v0.7.1, see
[CHANGELOG.md](CHANGELOG.md)). 473 postings scraped, cleaned, loaded, modeled,
visualized, and analyzed end to end.

---

## Table of Contents

- [What This Project Demonstrates](#what-this-project-demonstrates)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Data Source & Scraping Ethics](#data-source--scraping-ethics)
- [Installation](#installation)
- [Running the Pipeline](#running-the-pipeline-in-order)
- [Data Dictionary](#data-dictionary)
- [Analytical Surfaces](#analytical-surfaces)
- [Key Findings](#key-findings-full-writeup-in-docsmarket_analysismd)
- [Data Quality & Known Limitations](#data-quality--known-limitations)
- [Tech Stack](#tech-stack)
- [Roadmap](#roadmap--not-yet-built)
- [License](#license)

---

## What This Project Demonstrates

| Skill area | Where |
|---|---|
| Ethical web scraping (schema.org parsing, resumable crawl, retry/backoff, rate limiting) | `scripts/scraper.py` |
| Data cleaning at scale (dedup, currency normalization via live FX, long-format unpivoting) | `scripts/clean.py` |
| Relational data modeling (3NF-ish star: dimensions + many-to-many junctions) | `scripts/models.py`, `database/job_market.db` |
| SQL analysis (11 reusable views: aggregation, self-joins, window-style ranking) | `database/views.sql` |
| BI tool integration (Power BI star schema + DAX + 7-page report spec) | `dashboard/powerbi_data/`, `docs/powerbi_design_spec.md` |
| Exploratory data analysis (Plotly, executed end-to-end with real output) | `notebooks/eda.ipynb` |
| Front-end dashboard engineering (vanilla JS, Chart.js, client-side cross-filtering) | `dashboard/index.html`, `dashboard/executive_dashboard.html` |
| Analytical writing (quantified findings + self-caught data-quality issues) | `docs/market_analysis.md` |

---

## Architecture

```
                      ┌─────────────────────┐
                      │   Himalayas.app      │
                      │  (schema.org jobs)   │
                      └──────────┬───────────┘
                                 │  scripts/scraper.py
                                 │  (paginated crawl, resumable via seen_urls.json)
                                 ▼
                      data/raw/jobs_*.json  (git-ignored, point-in-time snapshots)
                                 │
                                 │  scripts/clean.py
                                 │  (dedup, FX-normalize salary, explode multi-value fields)
                                 ▼
                data/cleaned/{jobs_clean, job_countries, job_skills}.csv
                                 │
                                 │  scripts/load_database.py  (idempotent upsert)
                                 ▼
                      database/job_market.db  (SQLite, star-ish schema)
                                 │
                                 │  scripts/create_views.py
                                 ▼
                      database/views.sql  (11 analytical views)
                                 │
                ┌────────────────┼──────────────────────┐
                │                │                      │
   scripts/export_powerbi.py   scripts/export_dashboard_json.py   notebooks/eda.ipynb
                │                │                      │        (reads the DB directly)
                ▼                ▼                      ▼
   dashboard/powerbi_data/   dashboard/data/*.json   dashboard/eda_report.html
   (star-schema CSVs)              │
                │                  ├──► dashboard/index.html (fetch-based, 9 JSON files)
                ▼                  └──► dashboard/executive_dashboard.html
   Power BI Desktop report              (single file, raw postings embedded, live filters)
   (spec in docs/powerbi_design_spec.md)
```

Two dashboard-export scripts exist on purpose: `export_powerbi.py` ships
**row-level** star-schema CSVs because Power BI has its own aggregation
engine, while `export_dashboard_json.py` ships **pre-aggregated** JSON
because the static HTML dashboard has no query engine behind it.
`executive_dashboard.html` takes a third approach — it embeds the raw,
row-level postings (plus the country-eligibility bridge) directly in the page
and aggregates client-side in JavaScript, so its Experience/Work
Setup/Country filters recompute every chart and KPI live instead of only
toggling between pre-baked slices.

---

## Project Structure

```
JobMarketAnalysis/
├── config/
│   └── config.yaml              All tunable settings: scraper behavior, paths,
│                                 tracked skill keywords, logging
├── data/
│   ├── raw/                     Raw scrape dumps, JSON (git-ignored)
│   └── cleaned/                 Cleaned, analysis-ready CSVs (committed)
│       ├── jobs_clean.csv       One row per posting (wide)
│       ├── job_countries.csv    Long format: job_url ↔ eligible country
│       └── job_skills.csv       Long format: job_url ↔ detected skill
├── database/
│   ├── job_market.db            Normalized SQLite database (committed)
│   └── views.sql                11 analytical SQL views
├── dashboard/
│   ├── index.html / script.js / style.css   Fetch-based dashboard (9 JSON files)
│   ├── executive_dashboard.html             Self-contained, cross-filterable dashboard
│   ├── eda_report.html                      Executed Plotly notebook, exported to HTML
│   ├── data/                                Pre-aggregated JSON for index.html
│   └── powerbi_data/                        Star-schema CSVs for Power BI import
├── docs/
│   ├── powerbi_design_spec.md    Full 7-page Power BI report build spec (data model,
│   │                              DAX, page-by-page layout)
│   └── market_analysis.md        Written findings + explicit data-quality writeup
├── notebooks/
│   └── eda.ipynb                 Plotly EDA, executed end-to-end
├── scripts/
│   ├── config.py                 Central config loader (get_config())
│   ├── logger.py                 Centralized rotating-file logging
│   ├── scraper.py                 Stage 2 — collects raw postings
│   ├── clean.py                   Stage 3 — cleans + normalizes
│   ├── models.py                  Stage 4 — SQLAlchemy ORM schema
│   ├── load_database.py           Stage 4 — idempotent CSV → SQLite loader
│   ├── create_views.py             Stage 6 — applies views.sql to the DB
│   ├── export_powerbi.py           Stage 6 — DB → Power BI star-schema CSVs
│   └── export_dashboard_json.py    Stage 6 — DB → pre-aggregated dashboard JSON
├── logs/                          Rotating log files (git-ignored)
├── requirements.txt
├── CHANGELOG.md                   Stage-by-stage build history
├── LICENSE
└── README.md
```

---

## Data Source & Scraping Ethics

[Himalayas.app](https://himalayas.app) — chosen because its `robots.txt`
explicitly allows crawling (`Allow: /`) and job pages embed structured
`schema.org/JobPosting` JSON-LD, making extraction reliable without fragile
HTML scraping.

`scripts/scraper.py` is polite by construction, not just by intent:

- Identifying `User-Agent` naming the project and a contact address
- `request_delay_seconds: 2.0` between requests (configurable in `config/config.yaml`)
- Exponential backoff on retryable failures (`tenacity`, max 3 attempts)
- **Resumable**: previously-seen job URLs are tracked in
  `data/raw/seen_urls.json`, so re-running only fetches newly-posted jobs
  instead of re-crawling the entire site

---

## Installation

```bash
git clone https://github.com/hashtro9-rgb/JobMarketAnalysis.git
cd JobMarketAnalysis
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.10+ (developed against 3.12). No API keys or `.env` needed —
the only external network call is to the free, keyless
[Frankfurter](https://frankfurter.dev) exchange-rate API during cleaning, and
that has a fixed-rate fallback if it's unreachable.

## Running the Pipeline (in order)

The repo already ships with real scraped/cleaned/loaded data (`data/cleaned/`,
`database/job_market.db`, `dashboard/data/`), so you can explore the outputs
immediately without re-running anything. To regenerate from scratch:

```bash
# 1. Scrape (resumable — safe to re-run; only pulls new postings)
python -m scripts.scraper

# 2. Clean + normalize into data/cleaned/
python -m scripts.clean

# 3. Load into the SQLite database (idempotent upsert)
python -m scripts.load_database

# 4. Apply analytical SQL views
python -m scripts.create_views

# 5. Export for Power BI (star-schema CSVs) and the JSON dashboard
python -m scripts.export_powerbi
python -m scripts.export_dashboard_json
```

Then open any of:
- `dashboard/index.html` or `dashboard/executive_dashboard.html` — directly
  in a browser (or serve the `dashboard/` folder, e.g.
  `python -m http.server --directory dashboard`)
- `notebooks/eda.ipynb` — via `jupyter notebook`
- `dashboard/powerbi_data/*.csv` — import into Power BI Desktop per
  [`docs/powerbi_design_spec.md`](docs/powerbi_design_spec.md)

---

## Data Dictionary

### `data/cleaned/jobs_clean.csv` (one row per posting, 473 rows)

| Column | Type | Notes |
|---|---|---|
| `job_url` | string | Natural unique key (also the scraper's own dedup key) |
| `job_title_clean` | string | Whitespace-normalized title |
| `company_clean` | string | Whitespace-normalized company name |
| `primary_country` | string | First country if the posting lists several |
| `country` | string | Raw `;`-delimited list of all eligible countries |
| `country_count` | int | How many countries the posting is open to |
| `salary_min` / `salary_max` | float | As posted, original currency/period |
| `salary_currency`, `salary_period` | string | e.g. `USD`, `YEAR` |
| `salary_min_usd_annual` / `salary_max_usd_annual` / `salary_avg_usd_annual` | float | Annualized, FX-converted to USD |
| `employment_type` | string | `FULL_TIME`, `CONTRACTOR`, `TEMPORARY`, `INTERN`, `PART_TIME`, `OTHER` |
| `work_setup` | string | `Remote` or `Hybrid` (no on-site postings in this dataset) |
| `experience_level` | string | `Entry Level` / `Mid Level` / `Senior Level` / `Lead/Principal` / `Not Specified` |
| `skills_list` | string | `;`-delimited detected skills (keyword match, see `config/config.yaml`) |
| `skill_count` | int | Number of detected skills |
| `job_description` | text | HTML stripped |
| `posting_date`, `valid_through`, `scraped_at` | date/datetime | ISO 8601 |

### `data/cleaned/job_countries.csv` / `job_skills.csv` (long format)

Each row is one `(job_url, country)` or `(job_url, skill)` pair — this is
what makes "postings per country" and "postings per skill" countable
correctly when a job lists multiple values (818 country rows / ~1,663 skill
rows across 473 jobs; a naive one-row-per-job count would undercount both).

### Database schema (`scripts/models.py` → `database/job_market.db`)

- **`jobs`** — one row per posting, `job_url` unique. Salary, employment
  type, work setup, experience level, dates.
- **`companies`**, **`skills`**, **`locations`** — dimension tables, one row
  per unique value, populated get-or-create (idempotent).
- **`job_skills`**, **`job_locations`** — many-to-many junction tables. A
  junction (not a single FK) is required for locations specifically because
  many postings are open to multiple countries.

### SQL Views (`database/views.sql`, applied by `scripts/create_views.py`)

`v_jobs_enriched` · `v_skill_demand` · `v_top_companies` · `v_country_demand`
· `v_salary_by_skill` (min. 3 salaried postings) · `v_salary_by_experience` ·
`v_experience_distribution` · `v_work_setup_distribution` ·
`v_employment_type_distribution` · `v_monthly_trend` · `v_skill_cooccurrence`
(self-join for skill-pair demand)

### Power BI Star Schema (`dashboard/powerbi_data/`)

| File | Role | Rows |
|---|---|---|
| `fact_jobs.csv` | Fact table, one row per posting | 473 |
| `dim_companies.csv` | Company dimension | 352 |
| `dim_skills.csv` | Skill dimension | 18 |
| `dim_locations.csv` | Country dimension | 150 |
| `dim_date.csv` | Date dimension (day-grain, full posting window) | 122 |
| `bridge_job_skills.csv` | Job ↔ Skill many-to-many | ~1,663 |
| `bridge_job_locations.csv` | Job ↔ Country many-to-many | 818 |

Full relationship cardinalities, cross-filter directions, DAX measures, and
the 7-page report layout (Executive Summary, Job Market Overview, Salary
Analysis, Skills Analysis, Geographic Analysis, Hiring Trends, Company
Insights) are specified in
[`docs/powerbi_design_spec.md`](docs/powerbi_design_spec.md).

---

## Analytical Surfaces

| Surface | File | Description |
|---|---|---|
| **EDA notebook** | `notebooks/eda.ipynb` (`dashboard/eda_report.html` for the executed export) | Plotly, 14 sections: hiring companies, skills, job titles, geography, experience mix, remote/hybrid split, salary, salary-by-experience, skill combinations, monthly trend, key insights, next steps |
| **Fetch-based dashboard** | `dashboard/index.html` | 6 tabs (Overview/Skills/Salary/Geography/Trends/Jobs), loads 9 pre-aggregated JSON files, dark BI theme |
| **Executive dashboard** | `dashboard/executive_dashboard.html` | Single self-contained file, no external data fetches — embeds raw postings + country-eligibility data and computes every chart client-side, so Experience/Work Setup/Country filters recompute everything live. Includes an executive-summary insight panel. |
| **Power BI report** | Spec in `docs/powerbi_design_spec.md` + data in `dashboard/powerbi_data/` | 7-page report spec (a `.pbix` is a proprietary binary and can't be committed as source, so the spec + ready-to-import CSVs are the deliverable) |
| **Written analysis** | `docs/market_analysis.md` | Quantified findings, skill pay premiums, experience-level compensation curve, and self-audited data-quality issues |

---

## Key Findings

*(Full writeup with methodology notes in [`docs/market_analysis.md`](docs/market_analysis.md).)*

- **Fragmented market:** 352 employers for 473 postings; the top 10 employers
  combined account for only 11.2% of volume.
- **SQL is table stakes, not a differentiator:** in 78.9% of postings, but
  only a +1.2% salary premium over the $108,283 overall average.
- **R is the highest-leverage skill:** +15.8% salary premium despite
  appearing in only 20.5% of postings; Python is the best common/premium
  tradeoff (47.1% prevalence, +9.0% premium).
- **Entry-level roles are scarce:** only 4.0% of postings are tagged Entry
  Level, versus 26.9% Mid, 21.4% Senior, 2.3% Lead/Principal.
- **Remote-first but geographically concentrated:** 94.5% of postings are
  remote, yet the U.S. still accounts for 50.7% of all country-eligibility
  mentions.
- **Low salary transparency:** only 30.2% of postings disclose pay — every
  compensation figure here is drawn from that subset.

---

## Data Quality & Known Limitations

These were found by tracing anomalies back to the raw scrape files, not
assumed — see `docs/market_analysis.md` for the full detail:

1. **The monthly hiring trend has survivorship bias.** All raw scrape dumps
   in `data/raw/` are timestamped the same day — this pipeline takes a
   point-in-time snapshot of *currently live* postings, not a continuous
   crawl. Older months are undercounted because postings that have since
   been filled or expired have already disappeared from the source site.
2. **At least one salary outlier from a currency-tagging error upstream**
   (a Japan-based posting tagged `salary_currency: USD` with an implausible
   $500K–$800K range) measurably skews the "Not Specified" experience-level
   average. A sanity-check filter in `clean.py` (flag values outside
   roughly $15K–$300K for review) is the recommended fix, not yet implemented.
3. **Deduplication is exact-`job_url` only**, which misses same-employer
   reposts under a different company-page slug (a concrete example is
   documented in `market_analysis.md`).
4. **"Country demand" intentionally double-counts** postings open to
   multiple countries — correct for "where can I apply from," but per-country
   shares won't sum to 100% of postings.

---

## Tech Stack

`requests` + `beautifulsoup4` (scraping) · `pandas` + `numpy` (cleaning) ·
`sqlalchemy` (ORM + SQLite) · `pyyaml` (config) · `tenacity` (retry/backoff) ·
`lxml` (parsing) · `plotly` + `jupyter` (EDA) · `pytest` (testing scaffold) ·
vanilla JS + [Chart.js](https://www.chartjs.org/) (dashboards, via CDN, no
build step) · Power BI Desktop (BI report)

---

## Roadmap / Not Yet Built

The original scaffold reserved `.github/workflows/`, `tests/`, and `assets/`
directories for CI + scheduled scraper runs, automated tests, and chart
exports — these are placeholders for future work and are currently empty
(git doesn't track empty directories, so they won't appear in a fresh clone
until populated). Honest status, not a hidden gap:

- [ ] Unit tests for the cleaning/salary-normalization logic
- [ ] GitHub Actions workflow to re-run the scraper on a schedule
- [ ] The `clean.py` salary sanity-check filter described above
- [ ] Fuzzy (not just exact-URL) deduplication pass

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Gabriel Alegre Caña
