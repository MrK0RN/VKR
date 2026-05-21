from __future__ import annotations

import json
import logging
import logging.config
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

from app import config

_audit_file = None
_configured = False


def _audit_writer(log_dir: Path):
    path = log_dir / "hashimoto_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8")


def setup_logging() -> None:
    global _audit_file, _configured
    if _configured:
        return
    _configured = True

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
            },
            "handlers": {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": str(config.LOG_DIR / "hashimoto.log"),
                    "maxBytes": config.LOG_MAX_BYTES,
                    "backupCount": config.LOG_BACKUP_COUNT,
                    "encoding": "utf-8",
                    "formatter": "standard",
                },
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                },
            },
            "loggers": {
                "hashimoto": {
                    "handlers": ["file", "console"],
                    "level": config.LOG_LEVEL,
                    "propagate": False,
                },
            },
        }
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _audit_file = _audit_writer(config.LOG_DIR)


def get_logger(name: str = "hashimoto"):
    if not _configured:
        setup_logging()
    return structlog.get_logger(name).bind(logger=name)


def audit_log(event: str, **fields: Any) -> None:
    global _audit_file
    if _audit_file is None:
        setup_logging()
    record = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
        **fields,
    }
    _audit_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    _audit_file.flush()
