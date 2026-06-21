"""
Tests for processor.py.

These tests were written against the v1 sequential model and cover the
per-job processing logic in isolation. They pass trivially because they
call process_job() directly without concurrency — they do not exercise
the thread pool or the accumulator under concurrent access.
"""

import unittest
import logging

from nightproc import store, settings
from nightproc.processor import process_job, process_job_extended


def _make_logger():
    logger = logging.getLogger("test")
    logger.addHandler(logging.NullHandler())
    return logger


def _load_test_config():
    settings._cache = {
        "invoices": {"multiplier": 1.5, "processing_mode": "standard", "timeout_seconds": 30},
        "credits":  {"multiplier": 1.0, "processing_mode": "standard", "timeout_seconds": 30},
    }


class TestProcessJob(unittest.TestCase):

    def setUp(self):
        _load_test_config()
        self.accumulator = store.make_accumulator()
        self.logger = _make_logger()

    def test_successful_job_updates_accumulator(self):
        job = {"job_id": "j1", "category": "invoices", "payload": {"value": 100}, "retry_count": 0}
        result = process_job(job, self.accumulator, self.logger)
        self.assertTrue(result)
        self.assertEqual(self.accumulator.get("invoices_count"), 1)
        self.assertEqual(self.accumulator.get("invoices_total"), 150)

    def test_error_simulation_first_attempt_fails(self):
        job = {"job_id": "j2", "category": "invoices",
               "payload": {"value": 100, "error_simulation": True}, "retry_count": 0}
        result = process_job(job, self.accumulator, self.logger)
        self.assertFalse(result)
        self.assertNotIn("invoices_count", self.accumulator)

    def test_error_simulation_retry_succeeds(self):
        job = {"job_id": "j3", "category": "invoices",
               "payload": {"value": 100, "error_simulation": True}, "retry_count": 1}
        result = process_job(job, self.accumulator, self.logger)
        self.assertTrue(result)
        self.assertEqual(self.accumulator.get("invoices_count"), 1)

    def test_multiplier_applied(self):
        job = {"job_id": "j4", "category": "credits", "payload": {"value": 200}, "retry_count": 0}
        process_job(job, self.accumulator, self.logger)
        self.assertEqual(self.accumulator.get("credits_total"), 200)

    def test_multiple_jobs_accumulate(self):
        for i in range(5):
            job = {"job_id": f"j{i}", "category": "invoices",
                   "payload": {"value": 100}, "retry_count": 0}
            process_job(job, self.accumulator, self.logger)
        self.assertEqual(self.accumulator.get("invoices_count"), 5)
        self.assertEqual(self.accumulator.get("invoices_total"), 750)


class TestProcessJobExtended(unittest.TestCase):

    def setUp(self):
        _load_test_config()
        self.accumulator = store.make_accumulator()
        self.logger = _make_logger()

    def test_successful_extended_job(self):
        job = {"job_id": "j1", "category": "invoices", "payload": {"value": 100}, "retry_count": 0}
        result = process_job_extended(job, self.accumulator, self.logger)
        self.assertTrue(result)
        self.assertEqual(self.accumulator.get("invoices_count"), 1)

    def test_missing_value_field_fails(self):
        job = {"job_id": "j2", "category": "invoices", "payload": {}, "retry_count": 0}
        result = process_job_extended(job, self.accumulator, self.logger)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
