"""Applies the analytical SQL views in database/views.sql to the SQLite
database. Idempotent -- each view is DROP-then-CREATE, so re-running is safe."""
import sqlite3
from pathlib import Path

from scripts.config import get_config, project_root
from scripts.logger import get_logger

log = get_logger(__name__)


def main():
    cfg = get_config()
    db_path = Path(cfg["paths"]["database_path"])
    views_sql = (project_root() / "database" / "views.sql").read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    conn.executescript(views_sql)
    conn.commit()

    views = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    conn.close()

    log.info(f"Applied {len(views)} views to {db_path}")
    for (name,) in views:
        log.info(f"  - {name}")


if __name__ == "__main__":
    main()
