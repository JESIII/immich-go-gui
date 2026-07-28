"""Rotating file logger for the GUI. Qt-free."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config_manager import default_config_dir


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    log_dir = default_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "immich-go-gui.log"

    logger = logging.getLogger("immich_go_gui")
    logger.setLevel(level)
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(handler)
    return logger
