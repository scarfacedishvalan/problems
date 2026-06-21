"""
Batch job coordinator.

The Dispatcher class manages the job queue and worker pool.
Invoke run() to start processing all jobs and produce a report.

v1: jobs were processed sequentially in _process_all(). The dispatcher
iterated over self._jobs and called processor.dispatch_job() directly.
v2: _process_all() now loads jobs into a queue and a thread pool drains it.
The per-job logic is unchanged; only the execution model changed.
"""

import queue
import threading
import time

from nightproc import processor, report, store, history
from nightproc.util.counter import AtomicCounter
from nightproc.util.log import emit

_DEFAULT_THREAD_COUNT = 4
_DEFAULT_MAX_RETRIES = 3


class Dispatcher:
    """
    Coordinates job processing across a thread pool.

    Accepts a list of job dicts at construction. Call run() to start
    processing. Blocks until all jobs are complete and the report is written.
    """

    def __init__(self, jobs, thread_count=_DEFAULT_THREAD_COUNT,
                 max_retries=_DEFAULT_MAX_RETRIES, output_path="report.json"):
        self._jobs = jobs
        self._thread_count = thread_count
        self._max_retries = max_retries
        self._output_path = output_path

        # owned state
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._threads = []
        self._job_counter = AtomicCounter()
        self._accumulator = store.make_accumulator()

    def run(self, logger):
        """
        Process all jobs and write the report.

        Starts the worker pool, loads the job queue, waits for all tasks
        to complete (including retries), then triggers the reporter.
        """
        t_start = time.monotonic()

        self._start_workers(logger)

        # v1: iterated self._jobs here and called dispatch_job() directly
        # v2: load into queue for workers to pick up
        for job in self._jobs:
            self._queue.put(job)

        # block until every task_done() has been called — this includes retries
        self._queue.join()

        # all work is done; signal workers to exit their polling loops
        self._stop_event.set()
        for t in self._threads:
            t.join()

        elapsed = time.monotonic() - t_start

        report.generate(
            accumulator=self._accumulator,
            job_count=self._job_counter.value,
            output_path=self._output_path,
            logger=logger,
        )

        history.append_run({
            "job_count": self._job_counter.value,
            "output_path": self._output_path,
            "runtime_seconds": round(elapsed, 3),
        }, logger=logger)

    def _start_workers(self, logger):
        for i in range(self._thread_count):
            t = threading.Thread(
                target=_worker_loop,
                args=(
                    self._queue,
                    self._stop_event,
                    self._accumulator,
                    self._job_counter,
                    self._max_retries,
                    logger,
                ),
                name=f"worker-{i}",
                daemon=True,
            )
            self._threads.append(t)
            t.start()

    @property
    def accumulator(self):
        return self._accumulator

    @property
    def job_count(self):
        return self._job_counter.value


def _worker_loop(q, stop_event, accumulator, job_counter, max_retries, logger):
    """
    Worker thread body. Polls the queue until stop_event is set.

    On success: records result in accumulator, increments job counter,
                calls task_done().
    On transient failure: re-queues the job (adding a new task), then
                          calls task_done() for the current attempt.
    On permanent failure: records as failed, increments counter, calls task_done().
    """
    thread_id = threading.current_thread().name
    jobs_processed = 0

    while not stop_event.is_set():
        try:
            job = q.get(timeout=0.05)
        except queue.Empty:
            continue

        success = processor.dispatch_job(job, accumulator, logger)

        if success:
            job_counter.increment()
            jobs_processed += 1
            q.task_done()
        else:
            retry_count = job.get("retry_count", 0)
            if retry_count < max_retries:
                job["retry_count"] = retry_count + 1
                emit(logger, "job_retry",
                     job_id=job["job_id"],
                     category=job["category"],
                     retry_count=job["retry_count"],
                     reason="transient_failure",
                     thread_id=thread_id)
                q.put(job)       # new task added to queue
                q.task_done()    # current attempt is done
            else:
                store.update(accumulator, job["category"], 0, failed=True)
                job_counter.increment()
                jobs_processed += 1
                emit(logger, "job_failed",
                     job_id=job["job_id"],
                     category=job["category"],
                     final_retry_count=retry_count,
                     thread_id=thread_id)
                q.task_done()

    emit(logger, "worker_exit",
         thread_id=thread_id,
         jobs_processed=jobs_processed)
