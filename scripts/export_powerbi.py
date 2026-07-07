"""Exports the database as a Power BI-ready star schema to
dashboard/powerbi_data/*.csv.

Power BI *can* connect to SQLite directly, but only via a third-party ODBC
driver the reviewer would have to install. Exporting clean star-schema CSVs
instead makes the report import with zero setup ("Get Data > Text/CSV") and
keeps the files reviewable on GitHub.

Star schema produced:
    fact_jobs            one row per job (measures + dimension keys)
    dim_companies        company_id -> name/url
    dim_skills           skill_id -> name
    dim_locations        location_id -> country
    dim_date             one row per calendar day over the posting window,
                         with year/month/quarter attributes for Power BI's
                         time-intelligence (a dedicated Date dimension is
                         required for correct trend/YoY visuals)
    bridge_job_skills    many-to-many job<->skill
    bridge_job_locations many-to-many job<->country
"""
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from scripts.config import get_config
from scripts.logger import get_logger

log = get_logger(__name__)


def build_date_dimension(min_date, max_date) -> pd.DataFrame:
    """Continuous daily Date dimension spanning the posting window (padded to
    whole months), with the attributes Power BI needs for time intelligence."""
    start = pd.Timestamp(min_date).replace(day=1)
    end = (pd.Timestamp(max_date) + pd.offsets.MonthEnd(0))
    days = pd.date_range(start, end, freq="D")
    dim = pd.DataFrame({"date": days})
    dim["date_key"] = dim["date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["date"].dt.year
    dim["quarter"] = "Q" + dim["date"].dt.quarter.astype(str)
    dim["month_num"] = dim["date"].dt.month
    dim["month_name"] = dim["date"].dt.strftime("%B")
    dim["year_month"] = dim["date"].dt.strftime("%Y-%m")
    dim["week"] = dim["date"].dt.isocalendar().week.astype(int)
    dim["day_of_week"] = dim["date"].dt.strftime("%A")
    dim["date"] = dim["date"].dt.strftime("%Y-%m-%d")
    # reorder: key first
    return dim[["date_key", "date", "year", "quarter", "month_num",
                "month_name", "year_month", "week", "day_of_week"]]


def main():
    cfg = get_config()
    db_path = Path(cfg["paths"]["database_path"])
    out_dir = Path(cfg["paths"]["cleaned_dir"]).parent.parent / "dashboard" / "powerbi_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}")

    # --- fact table (one row per job, with a date_key for the Date dim) ---
    fact_jobs = pd.read_sql("""
        SELECT
            job_id, job_url, job_title, company_id, primary_location_id, city,
            salary_min_usd_annual, salary_max_usd_annual, salary_avg_usd_annual,
            salary_currency, employment_type, work_setup, experience_level,
            posting_date, valid_through
        FROM jobs
    """, engine)
    fact_jobs["date_key"] = (
        pd.to_datetime(fact_jobs["posting_date"], errors="coerce")
        .dt.strftime("%Y%m%d")
    )

    dim_companies = pd.read_sql("SELECT company_id, company_name, company_url FROM companies", engine)
    dim_skills = pd.read_sql("SELECT skill_id, skill_name FROM skills", engine)
    dim_locations = pd.read_sql("SELECT location_id, country_name FROM locations", engine)
    bridge_job_skills = pd.read_sql("SELECT job_id, skill_id FROM job_skills", engine)
    bridge_job_locations = pd.read_sql("SELECT job_id, location_id FROM job_locations", engine)

    valid_dates = pd.to_datetime(fact_jobs["posting_date"], errors="coerce").dropna()
    dim_date = build_date_dimension(valid_dates.min(), valid_dates.max())

    exports = {
        "fact_jobs": fact_jobs,
        "dim_companies": dim_companies,
        "dim_skills": dim_skills,
        "dim_locations": dim_locations,
        "dim_date": dim_date,
        "bridge_job_skills": bridge_job_skills,
        "bridge_job_locations": bridge_job_locations,
    }

    print("\n" + "=" * 60)
    print("POWER BI EXPORT")
    print("=" * 60)
    for name, df in exports.items():
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  {name:22s} {len(df):>5} rows -> {path.name}")
        log.info(f"Exported {name}: {len(df)} rows")
    print("=" * 60)
    print(f"Output dir: {out_dir}")


if __name__ == "__main__":
    main()
