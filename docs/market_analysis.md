# Data Analyst Job Market — Analysis & Recommendations

**Scope:** 473 Data Analyst postings scraped from Himalayas.app, live between
2026-04-10 and 2026-07-07. Snapshot collected 2026-07-07 (three scrape runs,
same day — see *Methodology & Data Quality* below for why this matters).

## Executive Summary

- The market is **broad and fragmented**, not concentrated: 352 unique
  employers for 473 postings (1.3 postings/employer), and the top 10 employers
  combined account for only 11.2% of volume. No single company dominates hiring.
- **SQL is table stakes, not a differentiator.** It appears in 78.9% of
  postings but carries almost no salary premium (+1.2% vs. the $108,283
  overall average) — it's a floor requirement, not a signal of seniority or pay.
- **Python and R are the clearest pay levers.** Python carries a +9.0% premium
  and appears in 47% of postings (still common enough to be worth learning);
  R carries the largest premium of any widely-used skill (+15.8%) despite
  appearing in only 20.5% of postings — it's the highest-leverage skill to add
  on top of a SQL/Tableau/Excel baseline.
- **Entry-level roles are scarce.** Only 4.0% of postings are tagged Entry
  Level, versus 26.9% Mid, 21.4% Senior, and 2.3% Lead/Principal (45.5% carry
  no experience tag at all). Early-career candidates are competing for a thin
  slice of the market.
- **Demand is geographically concentrated despite being remote-first.** 94.5%
  of postings are remote, yet the U.S. alone accounts for 50.7% of all
  country-eligibility mentions (818 mentions across 473 postings, since many
  postings list multiple eligible countries); the top 5 countries account for
  44.4%(*) of demand and 74 of 150 countries appear in only a single posting.
  ((*) figure computed on the un-deduplicated 818-mention base, consistent
  with the per-country breakdown above.)
- **Only 30.2% of postings disclose salary.** Every compensation figure in
  this analysis — including the ones above — is drawn from that 30% subset
  and should be read as directional, not representative of the full market.

## Compensation by Experience Level

| Level | Avg Salary | Median | n (salaried) |
|---|---|---|---|
| Entry Level | $75,473 | — | 7 |
| Mid Level | $91,675 | — | 46 |
| Senior Level | $111,162 | $107,845 | 42 |
| Lead/Principal | $139,129 | — | 5 |
| Not Specified | $124,992 | $87,550 | 43 |

Lead/Principal pays 84% more than Entry Level on average — a steep, fairly
linear seniority curve. The "Not Specified" bucket's mean ($124,992) is
noticeably higher than its own median ($87,550) and higher than the tagged
Senior Level mean — that gap is not a real signal, see below.

## Skill Pay Premiums (vs. $108,283 overall average, min. 3 salaried postings)

| Skill | Postings | % of market | Premium |
|---|---|---|---|
| R | 97 (20.5%) | +15.8% |
| Spark | 13 (2.7%) | +9.6% |
| Python | 223 (47.1%) | +9.0% |
| SQL | 373 (78.9%) | +1.2% |
| Tableau | 197 (41.6%) | −10.1% |
| Statistics | 108 (22.8%) | −13.6% |
| Excel | 184 (38.9%) | −16.5% |
| Power BI | 186 (39.3%) | −17.8% |
| AWS | 31 (6.6%) | −19.5% |

**Reading this table:** the negative-premium skills (Excel, Power BI, Tableau,
AWS) aren't "bad" skills — they're the most common ones, which pulls their
average toward the (lower) reporting/BI-tool end of the market. The
actionable takeaway is about the *combination*: SQL + Tableau/Power BI/Excel
is the baseline expected stack (confirmed by skill co-occurrence — Python+SQL
co-occurs 215 times, SQL+Tableau 181 times, Power BI+SQL 162 times); Python or
R on top of that baseline is what moves pay.

## Recommended Actions

1. **For job seekers:** treat SQL + one visualization tool (Tableau/Power BI)
   as the minimum bar, and prioritize Python or R next — R in particular is
   under-supplied relative to its pay premium.
2. **For early-career candidates:** given only 4% of postings target entry
   level, lean on referrals/networking rather than volume-applying to postings
   that don't specify a level (many "Not Specified" postings are likely
   senior roles that simply didn't tag experience — see below).
3. **For anyone reading the salary figures:** discount them proportionally —
   only 3 in 10 postings disclose pay, and the sample skews toward companies
   willing to be transparent, which may not represent the broader market.

## Methodology & Data Quality Notes

These are things I checked while building this analysis that materially
affect how much weight the headline numbers should carry:

- **The "monthly hiring trend" undercounts older months.** All three raw
  scrape dumps (`data/raw/jobs_2026070*.json`) are timestamped the same day,
  2026-07-07 — this pipeline takes a **point-in-time snapshot** of postings
  currently live on Himalayas, not a continuous crawl. Postings from April
  that have since been filled or expired have already disappeared from the
  site and this dataset, so April's low count (39) is partly an artifact of
  survivorship bias, not proof hiring was slower then. Only trust the
  month-over-month shape for the most recent 4–6 weeks before the scrape date;
  don't read it as a clean multi-month growth trend.
- **At least one clear salary outlier is inflating the "Not Specified"
  experience bucket.** Two nearly-identical Lennor Group "Data Analyst -
  Hybrid" postings for a Japan-based role list `salary_currency: "USD"` with
  min/max of $500,000–$800,000/year — implausible for the role and market,
  and consistent with a currency-tagging error upstream on the source listing
  (the role requires Japanese fluency and reads like a JPY figure mislabeled
  as USD). These two rows alone pull the "Not Specified" mean about $37K above
  its own median. **Recommendation:** add a sanity-check filter to
  `scripts/clean.py` (e.g., flag `salary_avg_usd_annual` outside roughly
  $15K–$300K for manual review) before it feeds salary aggregates.
- **Deduplication is exact-`job_url` only**, which misses same-employer
  reposts under a different company-page slug. The two Lennor Group Japan
  postings above are a concrete example: identical title, salary range, and
  country, posted under `/companies/lennor/...` and `/companies/lennor-group/...`
  respectively — same job, two URLs, both survive dedup. Worth a follow-up
  fuzzy-match pass (company + title + salary range) if precise counts matter.
- **"Country demand" intentionally counts multi-country eligibility, not a
  single primary country.** A posting open to 5 countries counts once per
  country (818 mentions across 473 postings). This is the right lens for "where
  can I apply from," but it means per-country shares don't sum to 100% —
  don't read them as a simple partition of the 473 postings.
