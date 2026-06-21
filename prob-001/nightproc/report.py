"""
Report generation.

Reads the accumulator after all workers have finished and writes a structured
JSON summary to disk. Also emits the run summary log line — the most useful
single diagnostic in the system. It prints both job_count (from the atomic
counter, always correct) and total_processed (from the accumulator count).
These must match on a correct run. The discrepancy field is zero on a clean run
and non-zero when the accumulator has lost or gained updates.
"""

import json
import time

from nightproc import store
from nightproc.util.log import emit


def generate(accumulator, job_count, output_path, logger):
    """
    Compute summary statistics and write the JSON report.

    Parameters
    ----------
    accumulator : dict
        Shared accumulator. Must only be called after all workers have finished.
    job_count : int
        Total jobs submitted, from the dispatcher's atomic counter. Ground truth.
    output_path : str
        Path to write the JSON report.
    logger : logging.Logger
    """
    emit(logger, "reporter_start")

    snapshot = store.read(accumulator)
    cat_names = store.categories(snapshot)

    categories_out = {}
    total_processed = 0   # count of successfully processed jobs (from accumulator)
    total_value = 0       # sum of result values
    failed_count = 0

    for cat in sorted(cat_names):
        cat_count = snapshot.get(f"{cat}_count", 0)
        cat_value = snapshot.get(f"{cat}_total", 0)
        cat_failed = snapshot.get(f"{cat}_failed", 0)
        categories_out[cat] = {
            "count": cat_count,
            "value": cat_value,
            "failed": cat_failed,
        }
        total_processed += cat_count
        total_value += cat_value
        failed_count += cat_failed

    run_id = _current_run_id()
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    # invariant: job_count == total_processed + failed_count
    # discrepancy is non-zero when the accumulator has been corrupted
    discrepancy = job_count - total_processed - failed_count

    report_data = {
        "run_id": run_id,
        "generated_at": generated_at,
        "job_count": job_count,
        "total_processed": total_processed,
        "total_value": total_value,
        "failed_count": failed_count,
        "discrepancy": discrepancy,
        "categories": categories_out,
    }

    with open(output_path, "w") as f:
        json.dump(report_data, f, indent=2)

    emit(
        logger,
        "reporter_complete",
        job_count=job_count,
        total_processed=total_processed,
        total_value=total_value,
        failed_count=failed_count,
        discrepancy=discrepancy,
        output_path=output_path,
    )

    return report_data


def _current_run_id():
    from nightproc.util.log import get_logger
    logger = get_logger()
    if logger and logger.handlers:
        fmt = logger.handlers[0].formatter
        if hasattr(fmt, "_run_id"):
            return fmt._run_id
    return "unknown"
