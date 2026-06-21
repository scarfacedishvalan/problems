# nightproc

Nightly batch job processor. Reads a queue of job descriptors, processes them
in parallel, and writes a structured summary report.

Requires Python 3.8+. No third-party dependencies.

---

## Quick Start

```bash
python run_batch.py jobs/sample_jobs.json
```

Output: `report.json` in the current directory. Logs: `logs/nightproc.log`.

---

## Usage

```
python run_batch.py <job_file> [options]

Arguments:
  job_file              Path to a JSON file containing an array of job descriptors

Options:
  --config PATH         Config file (default: config/default.json)
  --output PATH         Report output path (default: report.json)
  --threads N           Worker thread count (default: 4)
  --retries N           Max retries per failed job (default: 3)
  --log-dir PATH        Log directory (default: logs/)
  --keep-alive          Stay alive after the first run; read additional job file
                        paths from stdin (one per line). Useful during maintenance
                        windows to avoid repeated startup overhead.
```

### Examples

Run with default settings:
```bash
python run_batch.py jobs/sample_jobs.json
```

Run with more threads and a custom output path:
```bash
python run_batch.py jobs/sample_jobs.json --threads 8 --output /tmp/nightly_report.json
```

Run in keep-alive mode (pipe job files in):
```bash
echo "jobs/batch_a.json" | python run_batch.py jobs/batch_b.json --keep-alive
```

Or interactively:
```bash
python run_batch.py jobs/sample_jobs.json --keep-alive
# then type additional job file paths, one per line
# Ctrl-D to exit
```

---

## Job File Format

A job file is a JSON array of job descriptor objects.

```json
[
  {
    "job_id": "job-0001",
    "category": "invoices",
    "payload": { "value": 1250 },
    "retry_count": 0
  }
]
```

Fields:
- `job_id` — unique identifier (string)
- `category` — must match a key in the config `categories` block
- `payload.value` — numeric value to process
- `retry_count` — set to 0 for new jobs; managed automatically on retry

For testing transient failure handling, add `"error_simulation": true` to the payload.
The job will fail on its first attempt and succeed on retry.

---

## Config File Format

```json
{
  "categories": {
    "invoices": {
      "multiplier": 1.5,
      "processing_mode": "standard",
      "timeout_seconds": 30
    }
  },
  "defaults": {
    "multiplier": 1.0,
    "processing_mode": "standard",
    "timeout_seconds": 30
  }
}
```

`processing_mode` values:
- `standard` — fast path (~5ms per job)
- `extended` — slow path (~500ms per job); use for categories requiring heavy processing

---

## Report Format

```json
{
  "run_id": "run-1719792000",
  "generated_at": "2026-06-19T22:00:01",
  "job_count": 20,
  "total_processed": 20,
  "total_value": 18450,
  "failed_count": 0,
  "discrepancy": 0,
  "categories": {
    "invoices": { "count": 9, "value": 12450, "failed": 0 },
    "credits":  { "count": 5, "value": 4500,  "failed": 0 },
    "adjustments": { "count": 6, "value": 1500, "failed": 0 }
  }
}
```

`job_count` is the number of jobs that reached a terminal state (success or permanent failure).
`total_processed` is the count of successfully processed jobs from the accumulator.
`total_value` is the sum of processed job values from the accumulator.
`failed_count` is the count of permanently failed jobs from the accumulator.
`discrepancy` = `job_count - total_processed - failed_count`. Should be 0.

---

## Logs

Logs are written as JSON lines to `logs/nightproc.log` (rotating, max 10MB × 3 files)
and echoed to stderr.

Key events to look for:

| Event | When emitted |
|---|---|
| `config_load` | Once at startup, after config file is read |
| `job_start` | When a worker picks up a job |
| `job_complete` | After a job succeeds and is written to accumulator |
| `job_retry` | When a job fails and is re-queued |
| `job_failed` | When a job exhausts its retry limit |
| `worker_exit` | When a worker thread finishes |
| `reporter_start` | At the start of report generation |
| `reporter_complete` | After the report is written; includes `discrepancy` field |
| `run_history_append` | After run metadata is recorded; includes `history_length` |

---

## Running Tests

```bash
python -m unittest discover tests/
```

Tests run with a single worker thread for determinism. The test suite covers
per-job processing logic and was written before the thread pool was added in v2.
Multi-threaded behaviour is not covered by the test suite.

---

## Project Structure

```
run_batch.py          CLI entrypoint
nightproc/
  runner.py           Dispatcher — coordinates job queue and worker pool
  processor.py        Worker functions — fast and slow processing paths
  store.py            Accumulator — shared result collection
  settings.py         Config cache — loaded once at startup
  report.py           Reporter — reads accumulator, writes JSON report
  history.py          Run history — per-run audit log (in-memory)
  util/
    counter.py        Thread-safe atomic counter
    log.py            Structured JSON logging setup
config/
  default.json        Default per-category processing config
jobs/
  sample_jobs.json    Example job file for testing
tests/
  test_processor.py
  test_report.py
  test_runner.py
logs/                 Created at runtime
```

---

## History

v1 — sequential processor. Single-threaded, simple loop.
v2 — thread pool added for throughput. Core data structures and processing logic
     unchanged from v1. Threading layer added on top.
