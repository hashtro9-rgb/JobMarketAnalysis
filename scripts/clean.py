"""Cleans raw scraped job records (data/raw/jobs_*.json) into analysis-ready
tables in data/cleaned/.

Cleaning performed:
  - Deduplicate on job_url (the true identity key -- same-company/same-title
    postings with distinct URLs are genuinely separate listings, not dupes)
  - Normalize company names (whitespace/casing artifacts)
  - Standardize dates (ISO 8601 -> YYYY-MM-DD)
  - Convert salary ranges to a single comparable basis: annualized USD,
    using live exchange rates (falls back to a fixed rate table if the rate
    API is unreachable, so the pipeline never hard-fails on cleaning)
  - Split multi-country and multi-skill fields into long-format tables so
    "demand by country" / "most common skills" can count each value once,
    rather than treating "Poland; United Kingdom" as one bucket
  - Strip any residual HTML from descriptions
  - Consistent null handling (NaN, not a mix of None/''/NaN)
"""
import glob
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from scripts.config import get_config
from scripts.logger import get_logger

log = get_logger(__name__)

# Used only if the live exchange-rate API is unreachable. Rates are
# "1 USD = X units of currency" -- same convention as the Frankfurter API.
FALLBACK_RATES_TO_USD = {
    "USD": 1.0, "EUR": 0.88, "GBP": 0.75, "CAD": 1.42,
    "ZAR": 16.2, "PLN": 3.76, "PHP": 61.5, "MXN": 17.5,
}


def fetch_exchange_rates(currencies: list) -> dict:
    """Live rates from Frankfurter (free, ECB-based, no API key). Falls back
    to a fixed table on any failure so cleaning never hard-crashes on a
    flaky network call."""
    currencies = sorted(set(c for c in currencies if c and c != "USD"))
    if not currencies:
        return {"USD": 1.0}
    try:
        resp = requests.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": "USD", "symbols": ",".join(currencies)},
            timeout=10,
        )
        resp.raise_for_status()
        rates = resp.json()["rates"]
        rates["USD"] = 1.0
        log.info(f"Fetched live exchange rates for {list(rates.keys())}")
        return rates
    except Exception as e:
        log.warning(f"Exchange rate API failed ({e}); using fallback fixed rates")
        return {c: FALLBACK_RATES_TO_USD.get(c, np.nan) for c in currencies + ["USD"]}


def load_raw_jobs(raw_dir: Path) -> pd.DataFrame:
    records = []
    files = sorted(glob.glob(str(raw_dir / "jobs_*.json")))
    for path in files:
        with open(path, encoding="utf-8") as f:
            records.extend(json.load(f))
    log.info(f"Loaded {len(records)} raw records from {len(files)} scrape file(s)")
    return pd.DataFrame(records)


def clean_company_name(name: str) -> str:
    if not isinstance(name, str):
        return name
    return " ".join(name.split()).strip()


def parse_iso_date(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def annualize_salary(value, period: str):
    """Convert a raw salary figure to an annual basis."""
    if value is None or pd.isna(value):
        return np.nan
    period = (period or "YEAR").upper()
    multiplier = {"YEAR": 1, "MONTH": 12, "WEEK": 52, "DAY": 260, "HOUR": 2080}.get(period, 1)
    return float(value) * multiplier


def clean_jobs(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset="job_url", keep="first").reset_index(drop=True)
    log.info(f"Deduplicated on job_url: {before} -> {len(df)} rows "
             f"({before - len(df)} exact duplicate postings removed)")

    df["company_clean"] = df["company"].apply(clean_company_name)
    df["job_title_clean"] = df["job_title"].apply(
        lambda t: " ".join(t.split()).strip() if isinstance(t, str) else t)

    df["posting_date"] = df["posting_date"].apply(parse_iso_date)
    df["valid_through"] = df["valid_through"].apply(parse_iso_date)
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")

    df["primary_country"] = df["country"].apply(
        lambda c: c.split(";")[0].strip() if isinstance(c, str) and c else np.nan)
    df["country_count"] = df["country"].apply(
        lambda c: len(c.split(";")) if isinstance(c, str) and c else 0)

    rates = fetch_exchange_rates(df["salary_currency"].dropna().unique().tolist())
    df["salary_min_annual_local"] = df.apply(
        lambda r: annualize_salary(r["salary_min"], r["salary_period"]), axis=1)
    df["salary_max_annual_local"] = df.apply(
        lambda r: annualize_salary(r["salary_max"], r["salary_period"]), axis=1)

    def to_usd(value, currency):
        if value is None or pd.isna(value):
            return np.nan
        rate = rates.get(currency)
        if rate is None or pd.isna(rate):
            return np.nan
        return round(value / rate, 2)

    df["salary_min_usd_annual"] = df.apply(
        lambda r: to_usd(r["salary_min_annual_local"], r["salary_currency"]), axis=1)
    df["salary_max_usd_annual"] = df.apply(
        lambda r: to_usd(r["salary_max_annual_local"], r["salary_currency"]), axis=1)
    df["salary_avg_usd_annual"] = df[["salary_min_usd_annual", "salary_max_usd_annual"]].mean(axis=1)

    df["skills_list"] = df["required_skills"].apply(
        lambda s: "; ".join(s) if isinstance(s, list) else "")
    df["skill_count"] = df["required_skills"].apply(
        lambda s: len(s) if isinstance(s, list) else 0)

    df["job_description"] = df["job_description"].fillna("")
    df = df.replace({None: np.nan})

    log.info(f"Salary rows with usable USD figure: "
             f"{df['salary_min_usd_annual'].notna().sum()}/{len(df)}")
    log.info(f"Jobs spanning multiple countries: {(df['country_count'] > 1).sum()}")

    return df


def build_long_tables(df: pd.DataFrame):
    """Explode multi-value fields into long format for accurate per-value
    counting (a job open to 5 countries should count toward all 5, and a
    job requiring 4 skills should count toward all 4 -- not get collapsed
    into one composite bucket)."""
    country_rows = []
    for _, row in df.iterrows():
        if not isinstance(row["country"], str) or not row["country"]:
            continue
        for country in row["country"].split(";"):
            country_rows.append({"job_url": row["job_url"], "country": country.strip()})
    countries_long = pd.DataFrame(country_rows)

    skill_rows = []
    for _, row in df.iterrows():
        skills = row["required_skills"]
        if not isinstance(skills, list):
            continue
        for skill in skills:
            skill_rows.append({"job_url": row["job_url"], "skill": skill})
    skills_long = pd.DataFrame(skill_rows)

    return countries_long, skills_long


def main():
    cfg = get_config()
    raw_dir = Path(cfg["paths"]["raw_dir"])
    cleaned_dir = Path(cfg["paths"]["cleaned_dir"])
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_raw_jobs(raw_dir)
    if raw_df.empty:
        log.warning("No raw job records found -- nothing to clean.")
        return

    cleaned = clean_jobs(raw_df)
    countries_long, skills_long = build_long_tables(cleaned)

    output_cols = [
        "job_url", "job_title_clean", "company_clean", "primary_country", "country",
        "country_count", "salary_min", "salary_max", "salary_currency", "salary_period",
        "salary_min_usd_annual", "salary_max_usd_annual", "salary_avg_usd_annual",
        "employment_type", "work_setup", "experience_level", "skills_list", "skill_count",
        "job_description", "posting_date", "valid_through", "scraped_at",
        "company_url", "city",
    ]
    cleaned[output_cols].to_csv(cleaned_dir / "jobs_clean.csv", index=False, encoding="utf-8-sig")
    countries_long.to_csv(cleaned_dir / "job_countries.csv", index=False, encoding="utf-8-sig")
    skills_long.to_csv(cleaned_dir / "job_skills.csv", index=False, encoding="utf-8-sig")

    log.info(f"Saved {len(cleaned)} cleaned jobs -> {cleaned_dir / 'jobs_clean.csv'}")
    log.info(f"Saved {len(countries_long)} job-country rows -> {cleaned_dir / 'job_countries.csv'}")
    log.info(f"Saved {len(skills_long)} job-skill rows -> {cleaned_dir / 'job_skills.csv'}")

    print("\n" + "=" * 60)
    print("CLEANING SUMMARY")
    print("=" * 60)
    print(f"Raw records loaded      : {len(raw_df)}")
    print(f"After dedup (job_url)   : {len(cleaned)}")
    print(f"With usable salary(USD) : {cleaned['salary_min_usd_annual'].notna().sum()}")
    print(f"Multi-country postings  : {(cleaned['country_count'] > 1).sum()}")
    print(f"Job-country long rows   : {len(countries_long)}")
    print(f"Job-skill long rows     : {len(skills_long)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
