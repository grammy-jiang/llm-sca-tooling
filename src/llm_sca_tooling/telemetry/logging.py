"""Structured logging setup for package modules."""

from __future__ import annotations

import logging
import os

_HANDLER_MARKER = "_llm_sca_handler"


class StructuredFormatter(logging.Formatter):
    """Small standard-library formatter with stable contextual fields."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured once with the project formatter."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        logger = logging.getLogger(name)
        logger.setLevel(_configured_level())
        logger.propagate = True
        return logger

    logger = logging.getLogger(name)
    logger.setLevel(_configured_level())
    if not any(getattr(handler, _HANDLER_MARKER, False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def _configured_level() -> int:
    name = os.environ.get("LLM_SCA_LOG_LEVEL", "INFO").upper()
    return getattr(logging, name, logging.INFO)
