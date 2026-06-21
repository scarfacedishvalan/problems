"""
Logging setup for nightproc.

Emits JSON-structured log lines to a rotating file and stderr.
Call setup() once at process start before any other module initialises.
"""

import json
import logging
import logging.handlers
import os


_logger = None


def setup(run_id, log_dir="logs"):
    global _logger

    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("nightproc")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = _JsonFormatter(run_id)

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "nightproc.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(fmt)
    logger.addHandler(stderr_handler)

    _logger = logger
    return logger


def get_logger():
    return _logger


def emit(logger, event, **kwargs):
    """Emit a structured log event with an explicit event name and fields."""
    r = logger.makeRecord(
        logger.name, logging.INFO, fn="", lno=0, msg=event, args=(), exc_info=None
    )
    r.payload = {"event": event, **kwargs}
    logger.handle(r)


class _JsonFormatter(logging.Formatter):
    def __init__(self, run_id):
        super().__init__()
        self._run_id = run_id

    def format(self, record):
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "run_id": self._run_id,
        }
        if hasattr(record, "payload"):
            entry.update(record.payload)
        else:
            entry["message"] = record.getMessage()
        return json.dumps(entry)
