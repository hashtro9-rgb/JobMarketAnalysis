"""Loads data/cleaned/*.csv into the normalized SQLite database
(database/job_market.db), defined in scripts/models.py.

Idempotent: dimension tables (Company, Skill, Location) use get-or-create,
and Jobs are upserted on job_url, so re-running this after a fresh scrape +
clean just adds what's new instead of duplicating existing rows.
"""
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.config import get_config
from scripts.logger import get_logger
from scripts.models import Base, Company, Skill, Location, Job

log = get_logger(__name__)


def get_or_create(session, model, lookup: dict, defaults: dict = None):
    instance = session.query(model).filter_by(**lookup).first()
    if instance:
        return instance, False
    params = {**lookup, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    session.flush()  # assign PK without committing yet
    return instance, True


def parse_date(value):
    if pd.isna(value):
        return None
    return pd.to_datetime(value).date()


def load_jobs_into_db(cleaned_dir: Path, engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    jobs_df = pd.read_csv(cleaned_dir / "jobs_clean.csv")
    countries_df = pd.read_csv(cleaned_dir / "job_countries.csv")
    skills_df = pd.read_csv(cleaned_dir / "job_skills.csv")

    countries_by_job = countries_df.groupby("job_url")["country"].apply(list).to_dict()
    skills_by_job = skills_df.groupby("job_url")["skill"].apply(list).to_dict()

    new_jobs, updated_jobs, companies_created, skills_created, locations_created = 0, 0, 0, 0, 0

    for _, row in jobs_df.iterrows():
        company, created = get_or_create(
            session, Company, {"company_name": row["company_clean"]},
            {"company_url": row.get("company_url")},
        )
        companies_created += created

        primary_location = None
        if pd.notna(row.get("primary_country")):
            primary_location, created = get_or_create(
                session, Location, {"country_name": row["primary_country"]})
            locations_created += created

        job = session.query(Job).filter_by(job_url=row["job_url"]).first()
        is_new = job is None
        if job is None:
            job = Job(job_url=row["job_url"])

        job.job_title = row["job_title_clean"]
        job.company_id = company.company_id
        job.city = row.get("city") if pd.notna(row.get("city")) else None
        job.primary_location_id = primary_location.location_id if primary_location else None
        job.salary_min = row.get("salary_min") if pd.notna(row.get("salary_min")) else None
        job.salary_max = row.get("salary_max") if pd.notna(row.get("salary_max")) else None
        job.salary_currency = row.get("salary_currency") if pd.notna(row.get("salary_currency")) else None
        job.salary_period = row.get("salary_period") if pd.notna(row.get("salary_period")) else None
        job.salary_min_usd_annual = row.get("salary_min_usd_annual") if pd.notna(row.get("salary_min_usd_annual")) else None
        job.salary_max_usd_annual = row.get("salary_max_usd_annual") if pd.notna(row.get("salary_max_usd_annual")) else None
        job.salary_avg_usd_annual = row.get("salary_avg_usd_annual") if pd.notna(row.get("salary_avg_usd_annual")) else None
        job.employment_type = row.get("employment_type") if pd.notna(row.get("employment_type")) else None
        job.work_setup = row.get("work_setup") if pd.notna(row.get("work_setup")) else None
        job.experience_level = row.get("experience_level") if pd.notna(row.get("experience_level")) else None
        job.job_description = row.get("job_description", "")
        job.posting_date = parse_date(row.get("posting_date"))
        job.valid_through = parse_date(row.get("valid_through"))
        job.scraped_at = pd.to_datetime(row.get("scraped_at"), errors="coerce")

        if is_new:
            session.add(job)
            new_jobs += 1
        else:
            updated_jobs += 1
        session.flush()

        # many-to-many: skills
        job.skills = []
        for skill_name in skills_by_job.get(row["job_url"], []):
            skill, created = get_or_create(session, Skill, {"skill_name": skill_name})
            skills_created += created
            job.skills.append(skill)

        # many-to-many: locations (full country list, not just primary)
        job.locations = []
        for country_name in countries_by_job.get(row["job_url"], []):
            loc, created = get_or_create(session, Location, {"country_name": country_name})
            locations_created += created
            job.locations.append(loc)

    session.commit()
    session.close()

    log.info(f"Jobs: {new_jobs} new, {updated_jobs} updated")
    log.info(f"New dimension rows -- companies: {companies_created}, "
             f"skills: {skills_created}, locations: {locations_created}")
    return {
        "new_jobs": new_jobs, "updated_jobs": updated_jobs,
        "companies_created": companies_created,
        "skills_created": skills_created,
        "locations_created": locations_created,
    }


def main():
    cfg = get_config()
    cleaned_dir = Path(cfg["paths"]["cleaned_dir"])
    db_path = Path(cfg["paths"]["database_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}", echo=cfg["database"]["echo_sql"])
    Base.metadata.create_all(engine)
    log.info(f"Schema ready at {db_path}")

    stats = load_jobs_into_db(cleaned_dir, engine)

    print("\n" + "=" * 60)
    print("DATABASE LOAD SUMMARY")
    print("=" * 60)
    for k, v in stats.items():
        print(f"{k:20s}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
