"""
Run history tracking.

Appends a metadata entry after each batch run. Intended as the foundation
for an admin audit interface that was scoped out before v2 shipped.

The _runs list accumulates for the lifetime of the process. In normal
single-invocation use this is one entry. In --keep-alive mode the list
grows by one entry per run.
"""

import time

from nightproc.util.log import emit

# module-level run history — never cleared
_runs = []


def append_run(metadata, logger=None):
    """Append a run summary to the history list."""
    entry = {
        "run_id": metadata.get("run_id", _infer_run_id()),
        "started_at": metadata.get("started_at", ""),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "job_count": metadata.get("job_count", 0),
        "output_path": metadata.get("output_path", ""),
        "runtime_seconds": metadata.get("runtime_seconds", 0.0),
    }
    _runs.append(entry)

    if logger:
        emit(
            logger,
            "run_history_append",
            run_id=entry["run_id"],
            history_length=len(_runs),
            runtime_seconds=entry["runtime_seconds"],
        )

    return entry


def get_history():
    """Return the full run history list. Unused in normal operation."""
    return list(_runs)


def _infer_run_id():
    from nightproc.util.log import get_logger
    logger = get_logger()
    if logger and logger.handlers:
        fmt = logger.handlers[0].formatter
        if hasattr(fmt, "_run_id"):
            return fmt._run_id
    return f"run-{int(time.time())}"
