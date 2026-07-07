"""Scrapes Data Analyst job postings from Himalayas.app.

Two-phase crawl:
  1. Walk the paginated search results (/jobs/data-analyst?page=N) to collect
     job detail URLs.
  2. Visit each new (not-previously-seen) detail page and parse its
     schema.org JobPosting JSON-LD block into a flat record.

Resumable by design: previously-scraped job URLs are tracked in
data/raw/seen_urls.json and skipped on subsequent runs, so re-running this
script is cheap and only pulls newly-posted jobs -- this is what makes the
scheduled/incremental scraping (Stage 8) practical instead of re-crawling
~500 listings every time.
"""
import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from scripts.config import get_config
from scripts.logger import get_logger

log = get_logger(__name__)

JOB_LINK_PATTERN = re.compile(r"^/companies/[^/]+/jobs/[^/?]+$")
PAGE_PARAM_PATTERN = re.compile(r"[?&]page=(\d+)")
TAG_RE = re.compile(r"<[^>]+>")


class ScraperError(Exception):
    """Raised for non-retryable scraper failures."""


def _session(cfg: dict) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": cfg["scraper"]["user_agent"]})
    return s


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException,)),
    reraise=True,
)
def fetch(session: requests.Session, url: str, timeout: int) -> str:
    """GET a URL with retry + exponential backoff. Raises on non-200 so
    tenacity's retry wrapper can catch transient failures (5xx, timeouts)."""
    resp = session.get(url, timeout=timeout)
    if resp.status_code == 404:
        raise ScraperError(f"404 Not Found: {url}")
    resp.raise_for_status()
    return resp.text


def strip_html(raw_html: str) -> str:
    """Job descriptions come as HTML; keep this as plain text for storage."""
    if not raw_html:
        return ""
    text = TAG_RE.sub(" ", raw_html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def detect_skills(text: str, skill_keywords: list) -> list:
    """Case-insensitive whole-word match of configured skill keywords
    against title+description text. Returns the matched skills in their
    canonical (config-defined) casing."""
    if not text:
        return []
    upper = text.upper()
    found = []
    for kw in skill_keywords:
        pattern = r"\b" + re.escape(kw.upper()) + r"\b"
        if re.search(pattern, upper):
            found.append(kw)
    return found


def bucket_experience_level(months) -> str:
    """Heuristic bucketing of monthsOfExperience into a human-readable
    experience level -- Himalayas doesn't expose a direct 'level' field."""
    if months in (None, ""):
        return "Not Specified"
    try:
        m = int(months)
    except (TypeError, ValueError):
        return "Not Specified"
    if m <= 12:
        return "Entry Level"
    if m <= 36:
        return "Mid Level"
    if m <= 72:
        return "Senior Level"
    return "Lead/Principal"


def determine_work_setup(job_location_type: str, description: str) -> str:
    """Himalayas is primarily a remote-jobs board, so TELECOMMUTE covers most
    postings. For anything else, fall back to a keyword check on the
    description since the schema doesn't cleanly distinguish Hybrid."""
    if job_location_type == "TELECOMMUTE":
        desc_lower = (description or "").lower()
        if "hybrid" in desc_lower:
            return "Hybrid"
        return "Remote"
    if job_location_type in ("ONSITE",) or job_location_type is None:
        return "On-site"
    return job_location_type.title()


def _as_dict(value) -> dict:
    """Himalayas's JobPosting schema isn't perfectly consistent -- fields
    that are usually a structured object (experienceRequirements,
    hiringOrganization, baseSalary, jobLocation) occasionally come back as a
    free-text string instead (e.g. experienceRequirements: "no requirements").
    Callers expect a dict either way; this normalizes non-dict values to {}
    rather than letting `.get()` crash on a str."""
    return value if isinstance(value, dict) else {}


def parse_salary(base_salary) -> tuple:
    """Returns (min_salary, max_salary, currency, period) or (None, None, None, None)."""
    base_salary = _as_dict(base_salary)
    if not base_salary:
        return None, None, None, None
    value = _as_dict(base_salary.get("value"))
    return (
        value.get("minValue"),
        value.get("maxValue"),
        base_salary.get("currency"),
        value.get("unitText"),
    )


def parse_job_detail(html: str, url: str, skill_keywords: list) -> dict | None:
    """Extract the JobPosting JSON-LD block and map it to our flat schema.
    Returns None if the page has no JobPosting data (some listings lack it --
    logged and skipped by the caller, not treated as a hard failure)."""
    soup = BeautifulSoup(html, "lxml")
    posting = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            posting = data
            break

    if posting is None:
        return None

    description_html = posting.get("description", "")
    description = strip_html(description_html)
    title = posting.get("title", "")

    org = _as_dict(posting.get("hiringOrganization"))
    countries = [c.get("name") for c in (posting.get("applicantLocationRequirements") or [])
                 if isinstance(c, dict) and c.get("name")]
    job_location = _as_dict(posting.get("jobLocation"))
    addr = _as_dict(job_location.get("address"))
    city = addr.get("addressLocality")

    min_sal, max_sal, currency, period = parse_salary(posting.get("baseSalary"))
    exp_req = _as_dict(posting.get("experienceRequirements"))

    skills_title_desc = f"{title} {description}"

    return {
        "job_title": title,
        "company": org.get("name", ""),
        "company_url": org.get("url", ""),
        "city": city,
        "country": "; ".join(countries) if countries else None,
        "salary_min": min_sal,
        "salary_max": max_sal,
        "salary_currency": currency,
        "salary_period": period,
        "employment_type": posting.get("employmentType"),
        "work_setup": determine_work_setup(posting.get("jobLocationType"), description),
        "experience_level": bucket_experience_level(exp_req.get("monthsOfExperience")),
        "required_skills": detect_skills(skills_title_desc, skill_keywords),
        "job_description": description,
        "posting_date": posting.get("datePosted"),
        "valid_through": posting.get("validThrough"),
        "job_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def get_job_links_from_search_page(html: str) -> list:
    """Parse job detail links out of a search results page."""
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if JOB_LINK_PATTERN.match(href):
            links.add(href)
    return sorted(links)


def get_max_page_number(html: str) -> int:
    """Find the highest ?page=N link present (pagination control)."""
    soup = BeautifulSoup(html, "lxml")
    pages = []
    for a in soup.find_all("a", href=True):
        m = PAGE_PARAM_PATTERN.search(a["href"])
        if m:
            pages.append(int(m.group(1)))
    return max(pages) if pages else 1


def load_seen_urls(raw_dir: Path) -> set:
    path = raw_dir / "seen_urls.json"
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_urls(raw_dir: Path, seen: set):
    path = raw_dir / "seen_urls.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def run_scraper() -> Path:
    cfg = get_config()
    scraper_cfg = cfg["scraper"]
    raw_dir = Path(cfg["paths"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    session = _session(cfg)
    base_url = scraper_cfg["base_url"]
    search_path = scraper_cfg["search_path"]
    delay = scraper_cfg["request_delay_seconds"]
    timeout = scraper_cfg["timeout_seconds"]
    max_pages_cap = scraper_cfg["max_pages_per_run"]

    seen_urls = load_seen_urls(raw_dir)
    log.info(f"Loaded {len(seen_urls)} previously-seen job URLs (will be skipped)")

    # --- Phase 1: collect job links across all search result pages ---
    all_links = set()
    log.info(f"Fetching search page 1: {base_url}{search_path}")
    first_html = fetch(session, f"{base_url}{search_path}", timeout)
    all_links.update(get_job_links_from_search_page(first_html))
    max_page = min(get_max_page_number(first_html), max_pages_cap)
    log.info(f"Search reports {max_page} pages (capped at {max_pages_cap}); "
             f"{len(all_links)} links from page 1")
    time.sleep(delay)

    for page_num in range(2, max_page + 1):
        url = f"{base_url}{search_path}?page={page_num}"
        try:
            html = fetch(session, url, timeout)
        except (requests.RequestException, ScraperError) as e:
            log.warning(f"Failed to fetch search page {page_num}: {e}")
            continue
        links = get_job_links_from_search_page(html)
        log.info(f"  page {page_num}: {len(links)} links")
        all_links.update(links)
        time.sleep(delay)

    new_links = [l for l in all_links if l not in seen_urls]
    log.info(f"Total unique job links: {len(all_links)}. "
             f"New (not previously scraped): {len(new_links)}")

    # --- Phase 2: visit each new job detail page ---
    records = []
    skill_keywords = cfg["skills"]["keywords"]
    for i, link in enumerate(new_links, 1):
        url = f"{base_url}{link}"
        try:
            html = fetch(session, url, timeout)
        except (requests.RequestException, ScraperError) as e:
            log.warning(f"  [{i}/{len(new_links)}] Failed to fetch {url}: {e}")
            continue

        try:
            record = parse_job_detail(html, url, skill_keywords)
        except Exception as e:
            log.warning(f"  [{i}/{len(new_links)}] Failed to parse {url}: {e}")
            continue

        if record is None:
            log.info(f"  [{i}/{len(new_links)}] No JobPosting data on {url} -- skipping")
        else:
            records.append(record)
            if i % 10 == 0:
                log.info(f"  [{i}/{len(new_links)}] enriched")

        seen_urls.add(link)
        time.sleep(delay)

    # --- Save ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = raw_dir / f"jobs_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    save_seen_urls(raw_dir, seen_urls)

    log.info(f"Scrape complete: {len(records)} new job records saved to {out_path}")
    log.info(f"Total seen_urls now: {len(seen_urls)}")
    return out_path


if __name__ == "__main__":
    run_scraper()
