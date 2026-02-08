"""Structured JSON logging setup for all services."""

import json
import logging
import sys
from collections.abc import Sequence
from datetime import datetime, timezone

# Build the set of standard LogRecord attributes so we can extract
# extra fields added via `extra={...}` in log calls.
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    | {"message", "asctime"}
)


class JsonFormatter(logging.Formatter):
    """Single-line JSON log formatter for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                log_entry[key] = value

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(
    level: str = "INFO",
    suppress: Sequence[str] = (),
) -> None:
    """Configure root logger with JSON formatter to stdout.

    Args:
        level: Root log level (e.g. "INFO", "DEBUG").
        suppress: Logger names to set to WARNING (e.g. "confluent_kafka",
                  "celery", "kombu") to reduce noise from third-party libs.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    for name in suppress:
        logging.getLogger(name).setLevel(logging.WARNING)
