"""
Result accumulator for batch job processing.

Holds per-category running totals that workers update as jobs complete.
Named 'store' from an earlier prototype where results were written to disk
incrementally; the file-backed store was removed in v1.4 but the name stuck.

Key scheme (v1 flat layout):
  {category}_count   — number of successfully processed jobs
  {category}_total   — sum of result values
  {category}_failed  — number of permanently failed jobs

Thread safety: update() acquires a module-level lock around the full
read-modify-write sequence. This is required because workers run concurrently
and the update is not atomic.
"""

import threading

_lock = threading.Lock()


def make_accumulator():
    """Return a fresh empty accumulator dict."""
    return {}


def update(accumulator, category, value, failed=False):
    """
    Record one job result into the accumulator.

    Thread-safe: acquires _lock for the full read-modify-write.
    """
    with _lock:
        if failed:
            key = f"{category}_failed"
            accumulator[key] = accumulator.get(key, 0) + 1
        else:
            accumulator[f"{category}_count"] = accumulator.get(f"{category}_count", 0) + 1
            accumulator[f"{category}_total"] = accumulator.get(f"{category}_total", 0) + value


def read(accumulator):
    """Return a shallow copy of the accumulator. Safe to call after workers finish."""
    return dict(accumulator)


def categories(accumulator):
    """Return the set of category names present in the accumulator."""
    names = set()
    for key in accumulator:
        if key.endswith("_count") or key.endswith("_total") or key.endswith("_failed"):
            names.add(key.rsplit("_", 1)[0])
    return names
