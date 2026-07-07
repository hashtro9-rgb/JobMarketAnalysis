"""Exports aggregated JSON for the custom HTML/Chart.js dashboard
(dashboard/index.html) -> dashboard/data/*.json.

Distinct from export_powerbi.py (which exports row-level star-schema CSVs
for Power BI to aggregate itself) -- this script pre-aggregates everything,
since the dashboard is a static page with no query engine behind it.
"""
import json
import sqlite3
from itertools import combinations
from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.config import get_config
from scripts.logger import get_logger

log = get_logger(__name__)


def round_floats(records):
    for row in records:
        for k, v in row.items():
            if isinstance(v, float):
                row[k] = None if pd.isna(v) else round(v, 2)
    return records


def main():
    cfg = get_config()
    db_path = Path(cfg["paths"]["database_path"])
    out_dir = Path(cfg["paths"]["cleaned_dir"]).parent.parent / "dashboard" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)

    jobs = pd.read_sql("""
        SELECT j.job_id, j.job_title, c.company_name, l.country_name AS primary_country,
               j.employment_type, j.work_setup, j.experience_level,
               j.salary_avg_usd_annual, j.salary_min_usd_annual, j.salary_max_usd_annual,
               j.posting_date, j.job_url
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.company_id
        LEFT JOIN locations l ON j.primary_location_id = l.location_id
    """, conn)
    job_skills = pd.read_sql("""
        SELECT js.job_id, s.skill_name FROM job_skills js JOIN skills s ON js.skill_id = s.skill_id
    """, conn)
    job_locations = pd.read_sql("""
        SELECT jl.job_id, l.country_name FROM job_locations jl JOIN locations l ON jl.location_id = l.location_id
    """, conn)
    conn.close()

    # ---------------- summary.json ----------------
    with_salary = jobs["salary_avg_usd_annual"].notna()
    summary = {
        "total_jobs": int(len(jobs)),
        "total_companies": int(jobs["company_name"].nunique()),
        "total_countries": int(job_locations["country_name"].nunique()),
        "total_skills_tracked": int(job_skills["skill_name"].nunique()),
        "avg_salary_usd": round(float(jobs.loc[with_salary, "salary_avg_usd_annual"].mean()), 0),
        "median_salary_usd": round(float(jobs.loc[with_salary, "salary_avg_usd_annual"].median()), 0),
        "salary_coverage_pct": round(float(with_salary.mean() * 100), 1),
        "remote_pct": round(float((jobs["work_setup"] == "Remote").mean() * 100), 1),
        "hybrid_count": int((jobs["work_setup"] == "Hybrid").sum()),
        "date_range_start": jobs["posting_date"].min(),
        "date_range_end": jobs["posting_date"].max(),
        "top_skill": job_skills["skill_name"].value_counts().idxmax(),
        "top_company": jobs["company_name"].value_counts().idxmax(),
        "top_country": job_locations["country_name"].value_counts().idxmax(),
    }

    # ---------------- skills.json ----------------
    skill_counts = job_skills["skill_name"].value_counts().reset_index()
    skill_counts.columns = ["skill", "postings"]
    skill_counts["pct"] = (skill_counts["postings"] / len(jobs) * 100).round(1)
    skill_salary = (jobs.merge(job_skills, on="job_id")
                     .dropna(subset=["salary_avg_usd_annual"])
                     .groupby("skill_name")["salary_avg_usd_annual"]
                     .agg(["mean", "count"]).round(0).reset_index())
    skill_salary.columns = ["skill", "avg_salary", "n_salaried"]
    skills_df = skill_counts.merge(skill_salary, on="skill", how="left")
    skills_records = round_floats(skills_df.to_dict(orient="records"))

    # ---------------- companies.json ----------------
    company_counts = jobs["company_name"].value_counts().head(30).reset_index()
    company_counts.columns = ["company", "postings"]
    company_salary = (jobs.dropna(subset=["salary_avg_usd_annual"])
                       .groupby("company_name")["salary_avg_usd_annual"]
                       .agg(["mean", "count"]).round(0).reset_index())
    company_salary.columns = ["company", "avg_salary", "n_salaried"]
    companies_df = company_counts.merge(company_salary, on="company", how="left")
    companies_records = round_floats(companies_df.to_dict(orient="records"))

    # ---------------- countries.json ----------------
    country_counts = job_locations["country_name"].value_counts().reset_index()
    country_counts.columns = ["country", "postings"]
    countries_records = round_floats(country_counts.to_dict(orient="records"))

    # ---------------- distributions.json ----------------
    distributions = {
        "experience_level": jobs["experience_level"].value_counts().to_dict(),
        "work_setup": jobs["work_setup"].value_counts().to_dict(),
        "employment_type": jobs["employment_type"].value_counts().to_dict(),
    }

    # ---------------- salary_by_experience.json ----------------
    exp_order = ["Entry Level", "Mid Level", "Senior Level", "Lead/Principal", "Not Specified"]
    sal_exp = (jobs.dropna(subset=["salary_avg_usd_annual"])
               .groupby("experience_level")["salary_avg_usd_annual"]
               .agg(["mean", "min", "max", "count"]).round(0)
               .reindex(exp_order).dropna(how="all").reset_index())
    sal_exp.columns = ["experience_level", "avg_salary", "min_salary", "max_salary", "n_salaried"]
    salary_by_experience_records = round_floats(sal_exp.to_dict(orient="records"))

    # ---------------- monthly_trend.json ----------------
    jobs["posting_month"] = pd.to_datetime(jobs["posting_date"]).dt.to_period("M").astype(str)
    monthly = jobs.groupby("posting_month").size().reset_index(name="postings")
    monthly_records = monthly.to_dict(orient="records")

    # ---------------- skill_pairs.json ----------------
    pair_counter = Counter()
    for _, group in job_skills.groupby("job_id")["skill_name"]:
        for pair in combinations(sorted(set(group)), 2):
            pair_counter[pair] += 1
    skill_pairs_records = [
        {"skill_a": a, "skill_b": b, "co_occurrences": n}
        for (a, b), n in pair_counter.most_common(20)
    ]

    # ---------------- salary_distribution.json (histogram-ready raw values) ----------------
    salary_values = jobs.loc[with_salary, "salary_avg_usd_annual"].round(0).astype(int).tolist()

    # ---------------- jobs.json (row-level, for a browsable table) ----------------
    jobs_export = jobs.copy()
    jobs_export["skills_list"] = jobs_export["job_id"].map(
        job_skills.groupby("job_id")["skill_name"].apply(list).to_dict()
    )
    jobs_export["skills_list"] = jobs_export["skills_list"].apply(lambda x: x if isinstance(x, list) else [])
    jobs_cols = ["job_title", "company_name", "primary_country", "employment_type",
                 "work_setup", "experience_level", "salary_min_usd_annual",
                 "salary_max_usd_annual", "salary_avg_usd_annual", "posting_date",
                 "job_url", "skills_list"]
    jobs_records = round_floats(jobs_export[jobs_cols].to_dict(orient="records"))

    # ---------------- write everything ----------------
    exports = {
        "summary.json": summary,
        "skills.json": skills_records,
        "companies.json": companies_records,
        "countries.json": countries_records,
        "distributions.json": distributions,
        "salary_by_experience.json": salary_by_experience_records,
        "monthly_trend.json": monthly_records,
        "skill_pairs.json": skill_pairs_records,
        "salary_distribution.json": salary_values,
        "jobs.json": jobs_records,
    }

    print("\n" + "=" * 60)
    print("DASHBOARD JSON EXPORT")
    print("=" * 60)
    for name, data in exports.items():
        path = out_dir / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  {name:28s} {path.stat().st_size:>8,d} bytes")
        log.info(f"Exported {name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
