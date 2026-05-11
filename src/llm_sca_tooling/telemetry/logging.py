"""Structured logger helper for llm-sca-tooling.

Usage::

    from llm_sca_tooling.telemetry.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Processing %d files in %s", count, path)

Rich integration: in CLI contexts, ``llm_sca_tooling.cli.main`` configures
a ``RichHandler`` on the root logger before importing anything else.
``get_logger`` checks for existing handlers to avoid duplication.
"""

from __future__ import annotations

import logging
import os

__all__ = ["get_logger"]

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger for *name*, configuring a plain handler if needed.

    If the root logger already has handlers (e.g. from ``RichHandler`` set
    up by the CLI), this function does not add another one — it just returns
    the named logger.
    """
    global _CONFIGURED  # noqa: PLW0603
    logger = logging.getLogger(name)

    if not logging.root.handlers and not _CONFIGURED:
        level_name = os.environ.get("LLM_SCA_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, datefmt=_DATE_FORMAT))
        logging.root.addHandler(handler)
        logging.root.setLevel(level)
        _CONFIGURED = True

    return logger
