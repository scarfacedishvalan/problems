"""
Job processing functions.

process_job() handles standard jobs (fast path).
process_job_extended() handles jobs with processing_mode=extended (slow path).

Workers call these functions directly — each function writes its result to the
shared accumulator on success.

v1 note: these were called by the dispatcher loop directly, one at a time.
In v2 they run inside worker threads concurrently. The function signatures
are unchanged from v1.
"""

import threading
import time

from nightproc import store, settings
from nightproc.util.log import emit

# fast path: ~5ms per job
_FAST_PATH_SLEEP = 0.005

# slow path: ~500ms per job (extended processing mode)
_SLOW_PATH_SLEEP = 0.5


def process_job(job, accumulator, logger):
    """
    Fast path. Handles standard processing_mode jobs.

    Returns True on success, False on transient failure.
    Writes to accumulator only on confirmed success.
    """
    job_id = job["job_id"]
    category = job["category"]
    payload = job.get("payload", {})
    thread_id = threading.current_thread().name

    emit(logger, "job_start", job_id=job_id, category=category,
         processing_path="fast", thread_id=thread_id,
         retry_count=job.get("retry_count", 0))

    t0 = time.monotonic()
    time.sleep(_FAST_PATH_SLEEP)

    # simulate transient failure for jobs flagged with error_simulation
    if payload.get("error_simulation") and job.get("retry_count", 0) == 0:
        return False

    cfg = settings.get(category)
    result_value = int(payload.get("value", 0) * cfg["multiplier"])

    duration_ms = int((time.monotonic() - t0) * 1000)

    # write to accumulator only after confirming success
    store.update(accumulator, category, result_value)

    emit(logger, "job_complete", job_id=job_id, category=category,
         processing_path="fast", result_value=result_value,
         thread_id=thread_id, duration_ms=duration_ms)

    return True


def process_job_extended(job, accumulator, logger):
    """
    Slow path. Handles extended processing_mode jobs.

    Substantially slower than process_job() — performs additional
    validation and computation steps. Default ~500ms per job.
    Returns True on success, False on transient failure.
    Writes to accumulator only on confirmed success.
    """
    job_id = job["job_id"]
    category = job["category"]
    payload = job.get("payload", {})
    thread_id = threading.current_thread().name

    emit(logger, "job_start", job_id=job_id, category=category,
         processing_path="slow", thread_id=thread_id,
         retry_count=job.get("retry_count", 0))

    t0 = time.monotonic()

    # extended processing: validate payload structure, apply transformations
    # TODO: move validation into a separate validator module (backlog item #47)
    if "value" not in payload:
        return False

    time.sleep(_SLOW_PATH_SLEEP)

    if payload.get("error_simulation") and job.get("retry_count", 0) == 0:
        return False

    cfg = settings.get(category)
    result_value = int(payload.get("value", 0) * cfg["multiplier"])

    duration_ms = int((time.monotonic() - t0) * 1000)

    # write to accumulator only after confirming success
    store.update(accumulator, category, result_value)

    emit(logger, "job_complete", job_id=job_id, category=category,
         processing_path="slow", result_value=result_value,
         thread_id=thread_id, duration_ms=duration_ms)

    return True


def dispatch_job(job, accumulator, logger):
    """
    Route a job to the appropriate processing function based on config.

    v1: this was the only entry point, called directly in the loop.
    v2: called by worker threads.
    """
    cfg = settings.get(job.get("category", ""))
    mode = cfg.get("processing_mode", "standard")

    if mode == "extended":
        return process_job_extended(job, accumulator, logger)
    else:
        return process_job(job, accumulator, logger)
