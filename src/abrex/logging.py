"""Logging configuration for command-line and embedded applications."""

from __future__ import annotations

import logging
import sys
from typing import Final

DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(
    level: int | str = logging.INFO,
    *,
    log_format: str = DEFAULT_LOG_FORMAT,
) -> None:
    """Configure concise human-readable logging for an application boundary.

    The handler is installed at most once so repeated calls from tests or an
    embedding application do not duplicate messages.  Library modules only
    create child loggers; this is the sole configuration function.
    """

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    handler = next(
        (
            candidate
            for candidate in root_logger.handlers
            if getattr(candidate, "_abrex_handler", False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(sys.stderr)
        handler._abrex_handler = True  # type: ignore[attr-defined]
        root_logger.addHandler(handler)
    elif isinstance(handler, logging.StreamHandler):
        # Pytest and embedding applications may replace stderr between calls.
        # Keep the one application handler attached to the current stream.
        handler.stream = sys.stderr
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(log_format))
