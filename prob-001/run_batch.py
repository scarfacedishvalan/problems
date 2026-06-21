"""
nightproc — nightly batch job runner

Usage:
    python run_batch.py <job_file> [options]

Options:
    --config PATH       Config file path (default: config/default.json)
    --output PATH       Report output path (default: report.json)
    --threads N         Worker thread count (default: 4)
    --retries N         Max retries per job (default: 3)
    --keep-alive        Stay alive after first run; read additional job file
                        paths from stdin, one per line. Useful during maintenance
                        windows to avoid repeated startup overhead.
    --log-dir PATH      Log directory (default: logs/)
"""

import argparse
import json
import os
import sys
import time

from nightproc import settings
from nightproc.runner import Dispatcher
from nightproc.util import log


def parse_args():
    p = argparse.ArgumentParser(
        description="nightproc batch job runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("job_file", help="Path to job file (JSON array of job descriptors)")
    p.add_argument("--config", default="config/default.json", help="Config file path")
    p.add_argument("--output", default="report.json", help="Report output path")
    p.add_argument("--threads", type=int, default=4, help="Worker thread count")
    p.add_argument("--retries", type=int, default=3, help="Max retries per job")
    p.add_argument(
        "--keep-alive",
        action="store_true",
        help="Stay alive after first run; accept additional job files on stdin",
    )
    p.add_argument("--log-dir", default="logs", help="Log directory")
    return p.parse_args()


def load_jobs(job_file):
    with open(job_file, "r") as f:
        jobs = json.load(f)
    if not isinstance(jobs, list):
        raise ValueError(f"Job file must contain a JSON array, got {type(jobs)}")
    return jobs


def run_once(job_file, config_path, output_path, threads, retries, logger):
    jobs = load_jobs(job_file)
    d = Dispatcher(
        jobs=jobs,
        thread_count=threads,
        max_retries=retries,
        output_path=output_path,
    )
    d.run(logger=logger)


def main():
    args = parse_args()

    run_id = f"run-{int(time.time())}"
    logger = log.setup(run_id, log_dir=args.log_dir)

    # load config once — cached for the lifetime of the process
    settings.load(args.config)

    run_once(
        job_file=args.job_file,
        config_path=args.config,
        output_path=args.output,
        threads=args.threads,
        retries=args.retries,
        logger=logger,
    )

    if args.keep_alive:
        # accept additional job file paths from stdin
        # each line is a path to a job file; output path is reused
        print("nightproc: keep-alive mode. Enter job file paths (one per line). Ctrl-D to exit.")
        try:
            for line in sys.stdin:
                job_file = line.strip()
                if not job_file:
                    continue
                if not os.path.exists(job_file):
                    print(f"nightproc: file not found: {job_file}", file=sys.stderr)
                    continue
                run_once(
                    job_file=job_file,
                    config_path=args.config,
                    output_path=args.output,
                    threads=args.threads,
                    retries=args.retries,
                    logger=logger,
                )
        except EOFError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
