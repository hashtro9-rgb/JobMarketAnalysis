"""SQLAlchemy ORM schema for the normalized job market database.

Design notes:
  - Companies, Skills, Locations are dimension tables (one row per unique
    value) -- loaded via get-or-create so re-running the loader never
    creates duplicate dimension rows.
  - JobSkills and JobLocations are many-to-many junction tables. A
    JobLocations junction is required (not just a single FK on Jobs)
    because ~40 postings are open to multiple countries -- a single foreign
    key can't represent that.
  - Jobs.job_url is the natural unique key (matches the scraper's own
    dedup key), so re-loading is idempotent.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, Table,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

job_skills = Table(
    "job_skills", Base.metadata,
    Column("job_id", Integer, ForeignKey("jobs.job_id"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.skill_id"), primary_key=True),
)

job_locations = Table(
    "job_locations", Base.metadata,
    Column("job_id", Integer, ForeignKey("jobs.job_id"), primary_key=True),
    Column("location_id", Integer, ForeignKey("locations.location_id"), primary_key=True),
)


class Company(Base):
    __tablename__ = "companies"
    company_id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String, nullable=False, unique=True)
    company_url = Column(String)

    jobs = relationship("Job", back_populates="company")


class Skill(Base):
    __tablename__ = "skills"
    skill_id = Column(Integer, primary_key=True, autoincrement=True)
    skill_name = Column(String, nullable=False, unique=True)

    jobs = relationship("Job", secondary=job_skills, back_populates="skills")


class Location(Base):
    __tablename__ = "locations"
    location_id = Column(Integer, primary_key=True, autoincrement=True)
    country_name = Column(String, nullable=False, unique=True)

    jobs = relationship("Job", secondary=job_locations, back_populates="locations")


class Job(Base):
    __tablename__ = "jobs"
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_url = Column(String, nullable=False, unique=True)
    job_title = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id"))
    city = Column(String)
    primary_location_id = Column(Integer, ForeignKey("locations.location_id"))

    salary_min = Column(Float)
    salary_max = Column(Float)
    salary_currency = Column(String)
    salary_period = Column(String)
    salary_min_usd_annual = Column(Float)
    salary_max_usd_annual = Column(Float)
    salary_avg_usd_annual = Column(Float)

    employment_type = Column(String)
    work_setup = Column(String)
    experience_level = Column(String)
    job_description = Column(Text)

    posting_date = Column(Date)
    valid_through = Column(Date)
    scraped_at = Column(DateTime)

    company = relationship("Company", back_populates="jobs")
    primary_location = relationship("Location", foreign_keys=[primary_location_id])
    skills = relationship("Skill", secondary=job_skills, back_populates="jobs")
    locations = relationship("Location", secondary=job_locations, back_populates="jobs")

    __table_args__ = (UniqueConstraint("job_url", name="uq_job_url"),)
