"""Logging setup for delivery_worker (delegates to shared)."""

from shared.log import JsonFormatter, setup_logging as _setup

__all__ = ["JsonFormatter", "setup_logging"]


def setup_logging(level: str = "INFO") -> None:
    _setup(level, suppress=["celery", "kombu"])
