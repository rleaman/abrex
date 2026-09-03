"""Logging configuration for command-line and embedded applications."""

from __future__ import annotations

import logging
from typing import Final

DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(
    level: int | str = logging.INFO,
    *,
    log_format: str = DEFAULT_LOG_FORMAT,
) -> None:
    """Configure the process root logger for an application entry point."""

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    logging.basicConfig(level=level, format=log_format)
