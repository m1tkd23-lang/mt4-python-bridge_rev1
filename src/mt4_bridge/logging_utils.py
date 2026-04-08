# src\mt4_bridge\logging_utils.py
from __future__ import annotations

import logging
from pathlib import Path


_LOGGER_NAME = "mt4_bridge"
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_default_log_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "logs" / "mt4_bridge.log"


def setup_logging(log_path: Path | None = None) -> logging.Logger:
    resolved_log_path = log_path or get_default_log_path()
    resolved_log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(resolved_log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    logger.info("logging initialized: %s", resolved_log_path)
    return logger