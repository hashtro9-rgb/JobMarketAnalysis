# Power BI Report — Design Specification

This document is a complete build spec for the **Job Market Intelligence**
Power BI report. A `.pbix` file is a proprietary binary built in Power BI
Desktop and can't be generated as code, so this spec + the ready-to-import
star-schema CSVs (`dashboard/powerbi_data/`) are the deliverable: import the
data, wire up the model per §2, paste the DAX from §3, and build the seven
pages in §5.

---

## 1. Data Import

In Power BI Desktop: **Home → Get Data → Text/CSV**, and import all seven
files from `dashboard/powerbi_data/`:

| File | Role | Rows |
|------|------|------|
| `fact_jobs.csv` | Fact table (one row per posting) | 473 |
| `dim_companies.csv` | Company dimension | 352 |
| `dim_skills.csv` | Skill dimension | 18 |
| `dim_locations.csv` | Country dimension | 150 |
| `dim_date.csv` | Date dimension | 122 |
| `bridge_job_skills.csv` | Job ↔ Skill many-to-many | 1,663 |
| `bridge_job_locations.csv` | Job ↔ Country many-to-many | 818 |

After import, set data types explicitly:
`fact_jobs[posting_date]`, `valid_through` → **Date**;
`salary_*_usd_annual` → **Decimal Number**;
`dim_date[date]` → **Date**, `date_key` → **Whole Number**.

Mark **`dim_date` as the date table** (Table tools → Mark as Date Table →
`date` column). This is required for correct time-intelligence.

---

## 2. Data Model (Relationships)

Build these relationships in **Model view**. Cardinality and cross-filter
direction matter — get these right and every slicer just works.

| From (many) | To (one) | Cardinality | Cross-filter |
|-------------|----------|-------------|--------------|
| `fact_jobs[company_id]` | `dim_companies[company_id]` | Many-to-one | Single |
| `fact_jobs[primary_location_id]` | `dim_locations[location_id]` | Many-to-one | Single |
| `fact_jobs[date_key]` | `dim_date[date_key]` | Many-to-one | Single |
| `bridge_job_skills[job_id]` | `fact_jobs[job_id]` | Many-to-one | **Both** |
| `bridge_job_skills[skill_id]` | `dim_skills[skill_id]` | Many-to-one | Single |
| `bridge_job_locations[job_id]` | `fact_jobs[job_id]` | Many-to-one | **Both** |
| `bridge_job_locations[location_id]` | `dim_locations[location_id]` | Many-to-one | Single |

**Why "Both" on the bridge→fact links:** a skill slicer (from `dim_skills`)
needs to filter the fact table *through* the bridge. Setting the
`bridge_job_skills → fact_jobs` relationship to bidirectional lets a selected
skill filter every job-level visual. Same pattern for locations.

> Note: `dim_locations` connects to the fact table twice — once directly
> (`primary_location_id`, the single "headline" country) and once via the
> bridge (`bridge_job_locations`, the full multi-country list). Use the
> **bridge** for demand/geography analysis (a job open to 5 countries should
> count in all 5); use **primary_location** only when you need exactly one
> country per job. Keep the second (bridge) relationship active and the
> direct one inactive if Power BI flags ambiguity, and reference the direct
> one via `USERELATIONSHIP` in a measure only if needed.

---

## 3. DAX Measures

Create a dedicated measures table (**Enter Data → name it `_Measures`**,
delete its blank column) and add these:

```dax
Total Jobs = DISTINCTCOUNT( fact_jobs[job_id] )

Total Companies = DISTINCTCOUNT( fact_jobs[company_id] )

Jobs With Salary =
CALCULATE( [Total Jobs], NOT ISBLANK( fact_jobs[salary_avg_usd_annual] ) )

Salary Coverage % =
DIVIDE( [Jobs With Salary], [Total Jobs] )

Avg Salary (USD) = AVERAGE( fact_jobs[salary_avg_usd_annual] )

Median Salary (USD) = MEDIAN( fact_jobs[salary_avg_usd_annual] )

Min Salary (USD) = MIN( fact_jobs[salary_min_usd_annual] )

Max Salary (USD) = MAX( fact_jobs[salary_max_usd_annual] )

Remote Jobs =
CALCULATE( [Total Jobs], fact_jobs[work_setup] = "Remote" )

% Remote = DIVIDE( [Remote Jobs], [Total Jobs] )

Hybrid Jobs =
CALCULATE( [Total Jobs], fact_jobs[work_setup] = "Hybrid" )

Countries Covered = DISTINCTCOUNT( dim_locations[country_name] )

Skills Tracked = DISTINCTCOUNT( dim_skills[skill_name] )

Skill Postings = COUNTROWS( bridge_job_skills )   -- respects skill/job filters

% of Postings (Skill) =
DIVIDE( [Skill Postings], CALCULATE( [Total Jobs], ALL( dim_skills ) ) )

Postings MoM % =
VAR CurrentMonth = [Total Jobs]
VAR PrevMonth =
    CALCULATE( [Total Jobs], DATEADD( dim_date[date], -1, MONTH ) )
RETURN DIVIDE( CurrentMonth - PrevMonth, PrevMonth )
```

Formatting: salary measures → Currency ($, 0 decimals); the `%` measures →
Percentage (1 decimal).

---

## 4. Global Slicer Panel

Add these slicers to a left-hand panel and **sync them across all pages**
(View → Sync slicers). This satisfies the required interactive filters:

| Slicer | Field | Style |
|--------|-------|-------|
| Country | `dim_locations[country_name]` | Dropdown (searchable) |
| Company | `dim_companies[company_name]` | Dropdown (searchable) |
| Skill | `dim_skills[skill_name]` | List (multi-select) |
| Experience | `fact_jobs[experience_level]` | List |
| Work Setup | `fact_jobs[work_setup]` | Buttons |
| Posting Date | `dim_date[date]` | Between (date range) |

(City is intentionally omitted as a slicer — this remote-first dataset has
no city data. Note it on the report rather than adding a dead filter.)

---

## 5. Report Pages

Theme: dark canvas (`#0d1117` background, `#161b22` cards), accent blue
`#388bfd`, one accent per page. Consistent title bar top-left, KPI cards as a
top row, charts below.

### Page 1 — Executive Summary
Audience: leadership. One-screen answer to "what does this market look like?"
- **KPI cards (top row):** Total Jobs · Total Companies · Avg Salary (USD) ·
  % Remote · Countries Covered
- **Donut:** Work Setup (`work_setup`) — instantly shows the remote-first skew
- **Bar (horizontal):** Top 10 Skills — `dim_skills[skill_name]` by
  `[Skill Postings]`
- **Line:** Postings by month — `dim_date[year_month]` by `[Total Jobs]`
- **Card (text box):** a one-line auto-insight, e.g. *"SQL appears in 79% of
  postings — the near-universal baseline skill."*

### Page 2 — Job Market Overview
- **KPI cards:** Total Jobs · Full-Time % · Median Salary · Hybrid Jobs
- **Stacked bar:** Employment Type by Experience Level
- **Donut:** Experience Level distribution
- **Treemap:** Job Title (top 15) sized by count
- **Matrix:** Experience Level (rows) × Work Setup (cols), values = Total Jobs

### Page 3 — Salary Analysis
- **KPI cards:** Avg · Median · Min · Max Salary (USD) · Salary Coverage %
- **Histogram** (or binned column): salary distribution — bin
  `salary_avg_usd_annual` into 20k bands
- **Bar:** Avg Salary by Skill — `dim_skills[skill_name]` by
  `[Avg Salary (USD)]` (add a visual-level filter: `[Jobs With Salary] >= 3`)
- **Box-and-whisker** (custom visual) or column: Salary by Experience Level
- **Callout card:** *"Salary disclosed on only 30% of postings — read
  company/skill salary figures as directional."*

### Page 4 — Skills Analysis
- **KPI cards:** Skills Tracked · Avg Skills per Posting · Most-Requested Skill
- **Bar (horizontal):** all skills by `[Skill Postings]` with `% of Postings`
  as a secondary label
- **Matrix / heatmap:** skill co-occurrence — Skill A (rows) × Skill B (cols),
  values = co-occurrence count (source: `v_skill_cooccurrence`, or model it
  from the bridge). Conditional-format the cells as a heatmap.
- **Scatter:** Skill — X = `[Skill Postings]` (demand), Y =
  `[Avg Salary (USD)]` (pay). Upper-right quadrant = "high demand + high pay".

### Page 5 — Geographic Analysis
- **Filled map:** country demand — `dim_locations[country_name]` (via bridge)
  colored by `[Total Jobs]`
- **Bar:** Top 15 countries by posting count
- **Card:** % of postings open to multiple countries
- **Table:** Country · Postings · Avg Salary (USD)

### Page 6 — Hiring Trends
- **Line:** Postings by month (`dim_date[year_month]`) — the headline trend
- **Line (small multiples or overlay):** postings by month split by Experience
  Level
- **KPI card:** Postings MoM % (with up/down conditional color)
- **Area:** cumulative postings over time
- **Note card:** *"Trend covers Apr–Jul 2026; the scheduled scraper extends
  this window with each weekly run."*

### Page 7 — Company Insights
- **Bar:** Top 15 hiring companies by `[Total Jobs]`
- **Table:** Company · Postings · Avg Salary (USD) · Countries · Top Skill
- **Bar:** Avg Salary by Company (top payers, filter `[Jobs With Salary] >= 2`)
- **Slicer (on-page):** Experience Level, so a viewer can see which companies
  hire at each level

---

## 6. Interactions & Polish

- **Drill-through page** on Company: right-click any company → drill to a
  filtered detail page listing its individual postings (Title, Salary, Country,
  Skills, Posting Date, a URL button to the live listing).
- **Tooltips:** custom tooltip page showing per-skill mini-stats on hover.
- **Bookmarks:** an "Insights" bookmark that resets all slicers.
- **Buttons:** page-navigation buttons in the left panel matching the 7 pages.
- Export the finished report as `dashboard/JobMarketIntelligence.pbix` and add
  page screenshots to `assets/` for the README (Stage 7).

---

## 7. Refresh Workflow

The report imports from CSV, so refreshing after a new scrape is:

```bash
python scripts/scraper.py          # incremental: only new postings
python scripts/clean.py
python scripts/load_database.py
python scripts/create_views.py
python scripts/export_powerbi.py   # regenerates dashboard/powerbi_data/*.csv
```

Then **Home → Refresh** in Power BI Desktop picks up the regenerated CSVs. No
model rebuild needed — the schema is stable.
