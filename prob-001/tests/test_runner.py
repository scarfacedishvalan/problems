"""
Tests for runner.py.

Coverage here focuses on the sequential dispatch behaviour inherited from v1.
The Dispatcher is tested with thread_count=1 to keep tests deterministic.
Multi-threaded behaviour is not tested — the v1 test suite predates the
thread pool and was not extended when threading was added.
"""

import logging
import os
import tempfile
import unittest

from nightproc import settings
from nightproc.runner import Dispatcher


def _make_logger():
    logger = logging.getLogger("test_runner")
    logger.addHandler(logging.NullHandler())
    return logger


def _load_test_config():
    settings._cache = {
        "invoices": {"multiplier": 1.0, "processing_mode": "standard", "timeout_seconds": 30},
        "credits":  {"multiplier": 1.0, "processing_mode": "standard", "timeout_seconds": 30},
    }


class TestDispatcher(unittest.TestCase):

    def setUp(self):
        _load_test_config()
        self.logger = _make_logger()
        self.tmpdir = tempfile.mkdtemp()

    def _output(self):
        return os.path.join(self.tmpdir, "report.json")

    def _make_jobs(self, n, category="invoices", value=100):
        return [
            {"job_id": f"j{i}", "category": category,
             "payload": {"value": value}, "retry_count": 0}
            for i in range(n)
        ]

    def test_all_jobs_processed(self):
        jobs = self._make_jobs(10)
        d = Dispatcher(jobs, thread_count=1, output_path=self._output())
        d.run(self.logger)
        self.assertEqual(d.job_count, 10)

    def test_report_written(self):
        out = self._output()
        jobs = self._make_jobs(5)
        d = Dispatcher(jobs, thread_count=1, output_path=out)
        d.run(self.logger)
        self.assertTrue(os.path.exists(out))

    def test_empty_job_list(self):
        d = Dispatcher([], thread_count=1, output_path=self._output())
        d.run(self.logger)
        self.assertEqual(d.job_count, 0)

    def test_retry_jobs_eventually_succeed(self):
        # job-0 will fail on first attempt, succeed on retry
        jobs = [
            {"job_id": "j0", "category": "invoices",
             "payload": {"value": 100, "error_simulation": True}, "retry_count": 0},
            {"job_id": "j1", "category": "invoices",
             "payload": {"value": 100}, "retry_count": 0},
        ]
        d = Dispatcher(jobs, thread_count=1, max_retries=3, output_path=self._output())
        d.run(self.logger)
        self.assertEqual(d.job_count, 2)

    def test_multiple_threads_process_all_jobs(self):
        # sanity check that multi-threaded run completes without dropping jobs
        jobs = self._make_jobs(20)
        d = Dispatcher(jobs, thread_count=4, output_path=self._output())
        d.run(self.logger)
        self.assertEqual(d.job_count, 20)


if __name__ == "__main__":
    unittest.main()
