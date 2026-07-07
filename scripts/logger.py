"""Centralized logging -- every module calls get_logger(__name__) instead of
using print() or configuring logging ad hoc."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from scripts.config import get_config

_CONFIGURED = False


def _configure_root():
    global _CONFIGURED
    if _CONFIGURED:
        return

    cfg = get_config()
    log_cfg = cfg.get("logging", {})
    logs_dir = Path(cfg["paths"]["logs_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        logs_dir / "job_market_analysis.log",
        maxBytes=log_cfg.get("rotate_max_bytes", 5_000_000),
        backupCount=log_cfg.get("rotate_backup_count", 5),
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)
