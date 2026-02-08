"""Logging setup for event_gateway (delegates to shared)."""

from shared.log import JsonFormatter, setup_logging as _setup

__all__ = ["JsonFormatter", "setup_logging"]


def setup_logging(level: str = "INFO") -> None:
    _setup(level, suppress=["confluent_kafka"])
