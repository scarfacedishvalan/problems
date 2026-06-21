"""
Per-category processing configuration.

Loads config from disk at startup and caches it for the duration of the process.
Workers call get() during job processing to retrieve category parameters.

Named 'settings' rather than 'config' to avoid shadowing the stdlib configparser.
"""

import json
import os

# module-level cache — populated by load(), never refreshed
_cache = {}
_config_path = None
_load_timestamp = None


def load(path):
    """Load and cache configuration from a JSON file. Call once at startup."""
    global _cache, _config_path, _load_timestamp

    import time
    from nightproc.util.log import get_logger, emit

    _config_path = os.path.abspath(path)
    _load_timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(_config_path, "r") as f:
        raw = json.load(f)

    _cache = raw.get("categories", {})
    _defaults = raw.get("defaults", {})

    # backfill any missing fields from defaults
    for cat in _cache:
        for key, val in _defaults.items():
            _cache[cat].setdefault(key, val)

    logger = get_logger()
    if logger:
        emit(
            logger,
            "config_load",
            path=_config_path,
            load_timestamp=_load_timestamp,
            category_count=len(_cache),
            categories=list(_cache.keys()),
        )

    return _cache


def get(category):
    """Return config entry for the given category, or defaults if unknown."""
    return _cache.get(category, {
        "multiplier": 1.0,
        "processing_mode": "standard",
        "timeout_seconds": 30,
    })


def loaded_at():
    return _load_timestamp
