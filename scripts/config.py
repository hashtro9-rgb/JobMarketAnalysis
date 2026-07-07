"""Central config loader -- every script imports get_config() instead of
reading config.yaml directly or hardcoding values."""
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "config.yaml"


@lru_cache(maxsize=1)
def get_config() -> dict:
    """Load config.yaml once per process. Paths are resolved to absolute,
    anchored at the project root, so scripts work regardless of cwd."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    paths = cfg.setdefault("paths", {})
    for key in ("raw_dir", "cleaned_dir", "logs_dir"):
        if key in paths:
            paths[key] = str(ROOT / paths[key])
    if "database_path" in paths:
        paths["database_path"] = str(ROOT / paths["database_path"])

    return cfg


def project_root() -> Path:
    return ROOT
