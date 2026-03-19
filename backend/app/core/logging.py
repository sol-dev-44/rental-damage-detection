import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON-ish structured log formatter for consistent, parseable output."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        message = record.getMessage()

        log_entry = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }

        # Include extra fields set via `extra={}` on log calls
        for key in ("tenant_id", "user_id", "request_id", "inspection_id", "asset_id"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = str(value)

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        parts = [f"{k}={v}" for k, v in log_entry.items()]
        return " | ".join(parts)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Clear existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for logger_name in ("uvicorn.access", "sqlalchemy.engine", "boto3", "botocore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Convenience wrapper."""
    return logging.getLogger(name)
