-- ============================================================
-- Analytical SQL views for the Job Market Intelligence database.
--
-- These answer the project's core business questions directly in SQL and
-- serve as clean, reusable query surfaces for the Power BI report, the
-- notebook, and any ad-hoc SQL client. Re-runnable: each view is dropped
-- and recreated.
-- ============================================================

-- ------------------------------------------------------------
-- v_jobs_enriched : one flat, denormalized row per job.
-- The primary fact surface for BI tools that prefer a wide table.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_jobs_enriched;
CREATE VIEW v_jobs_enriched AS
SELECT
    j.job_id,
    j.job_title,
    c.company_name,
    l.country_name          AS primary_country,
    j.city,
    j.employment_type,
    j.work_setup,
    j.experience_level,
    j.salary_min_usd_annual,
    j.salary_max_usd_annual,
    j.salary_avg_usd_annual,
    j.salary_currency,
    j.posting_date,
    j.valid_through,
    strftime('%Y-%m', j.posting_date)  AS posting_month,
    j.job_url
FROM jobs j
LEFT JOIN companies c ON j.company_id = c.company_id
LEFT JOIN locations l ON j.primary_location_id = l.location_id;

-- ------------------------------------------------------------
-- v_skill_demand : how often each skill is requested.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_skill_demand;
CREATE VIEW v_skill_demand AS
SELECT
    s.skill_name,
    COUNT(*)                                                   AS postings,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM jobs), 1)   AS pct_of_postings
FROM job_skills js
JOIN skills s ON js.skill_id = s.skill_id
GROUP BY s.skill_name
ORDER BY postings DESC;

-- ------------------------------------------------------------
-- v_top_companies : which companies post the most analyst roles.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_top_companies;
CREATE VIEW v_top_companies AS
SELECT
    c.company_name,
    COUNT(*) AS postings
FROM jobs j
JOIN companies c ON j.company_id = c.company_id
GROUP BY c.company_name
ORDER BY postings DESC;

-- ------------------------------------------------------------
-- v_country_demand : demand per country, via the job_locations
-- junction so multi-country postings count toward every country.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_country_demand;
CREATE VIEW v_country_demand AS
SELECT
    l.country_name,
    COUNT(*) AS postings
FROM job_locations jl
JOIN locations l ON jl.location_id = l.location_id
GROUP BY l.country_name
ORDER BY postings DESC;

-- ------------------------------------------------------------
-- v_salary_by_skill : avg/min/max annualized-USD salary per skill,
-- restricted to skills with at least 3 salaried postings so the
-- averages aren't driven by a single outlier.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_salary_by_skill;
CREATE VIEW v_salary_by_skill AS
SELECT
    s.skill_name,
    ROUND(AVG(j.salary_avg_usd_annual), 0) AS avg_salary_usd,
    ROUND(MIN(j.salary_avg_usd_annual), 0) AS min_salary_usd,
    ROUND(MAX(j.salary_avg_usd_annual), 0) AS max_salary_usd,
    COUNT(*)                                AS n_salaried_postings
FROM job_skills js
JOIN skills s ON js.skill_id = s.skill_id
JOIN jobs j   ON js.job_id = j.job_id
WHERE j.salary_avg_usd_annual IS NOT NULL
GROUP BY s.skill_name
HAVING COUNT(*) >= 3
ORDER BY avg_salary_usd DESC;

-- ------------------------------------------------------------
-- v_salary_by_experience : salary summary per experience level.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_salary_by_experience;
CREATE VIEW v_salary_by_experience AS
SELECT
    experience_level,
    ROUND(AVG(salary_avg_usd_annual), 0) AS avg_salary_usd,
    COUNT(salary_avg_usd_annual)         AS n_salaried_postings,
    COUNT(*)                             AS n_total_postings
FROM jobs
GROUP BY experience_level
ORDER BY avg_salary_usd DESC;

-- ------------------------------------------------------------
-- v_experience_distribution
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_experience_distribution;
CREATE VIEW v_experience_distribution AS
SELECT experience_level, COUNT(*) AS postings
FROM jobs GROUP BY experience_level ORDER BY postings DESC;

-- ------------------------------------------------------------
-- v_work_setup_distribution
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_work_setup_distribution;
CREATE VIEW v_work_setup_distribution AS
SELECT work_setup, COUNT(*) AS postings
FROM jobs GROUP BY work_setup ORDER BY postings DESC;

-- ------------------------------------------------------------
-- v_employment_type_distribution
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_employment_type_distribution;
CREATE VIEW v_employment_type_distribution AS
SELECT employment_type, COUNT(*) AS postings
FROM jobs GROUP BY employment_type ORDER BY postings DESC;

-- ------------------------------------------------------------
-- v_monthly_trend : postings per calendar month.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_monthly_trend;
CREATE VIEW v_monthly_trend AS
SELECT
    strftime('%Y-%m', posting_date) AS posting_month,
    COUNT(*)                        AS postings
FROM jobs
WHERE posting_date IS NOT NULL
GROUP BY posting_month
ORDER BY posting_month;

-- ------------------------------------------------------------
-- v_skill_cooccurrence : how often skill pairs appear together.
-- Self-join on the junction table with a < b to count each unordered
-- pair once. A concise demonstration of SQL beyond simple GROUP BYs.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_skill_cooccurrence;
CREATE VIEW v_skill_cooccurrence AS
SELECT
    s1.skill_name AS skill_a,
    s2.skill_name AS skill_b,
    COUNT(*)      AS co_occurrences
FROM job_skills js1
JOIN job_skills js2 ON js1.job_id = js2.job_id AND js1.skill_id < js2.skill_id
JOIN skills s1 ON js1.skill_id = s1.skill_id
JOIN skills s2 ON js2.skill_id = s2.skill_id
GROUP BY s1.skill_name, s2.skill_name
ORDER BY co_occurrences DESC;
