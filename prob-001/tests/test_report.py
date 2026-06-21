"""Tests for report.py."""

import json
import logging
import os
import tempfile
import unittest

from nightproc import store
from nightproc.report import generate


def _make_logger():
    logger = logging.getLogger("test_report")
    logger.addHandler(logging.NullHandler())
    return logger


class TestGenerate(unittest.TestCase):

    def setUp(self):
        self.logger = _make_logger()
        self.tmpdir = tempfile.mkdtemp()

    def _output_path(self):
        return os.path.join(self.tmpdir, "report.json")

    def test_report_written_to_disk(self):
        acc = store.make_accumulator()
        store.update(acc, "invoices", 1000)
        out = self._output_path()
        generate(acc, job_count=1, output_path=out, logger=self.logger)
        self.assertTrue(os.path.exists(out))

    def test_total_processed_counts_jobs_not_values(self):
        acc = store.make_accumulator()
        store.update(acc, "invoices", 1500)
        store.update(acc, "invoices", 750)
        store.update(acc, "credits", 200)
        out = self._output_path()
        data = generate(acc, job_count=3, output_path=out, logger=self.logger)
        self.assertEqual(data["total_processed"], 3)
        self.assertEqual(data["total_value"], 2450)
        self.assertEqual(data["job_count"], 3)

    def test_discrepancy_zero_on_correct_run(self):
        acc = store.make_accumulator()
        store.update(acc, "invoices", 100)
        store.update(acc, "credits", 200)
        out = self._output_path()
        data = generate(acc, job_count=2, output_path=out, logger=self.logger)
        self.assertEqual(data["discrepancy"], 0)

    def test_failed_jobs_recorded(self):
        acc = store.make_accumulator()
        store.update(acc, "invoices", 1000)
        store.update(acc, "invoices", 0, failed=True)
        out = self._output_path()
        data = generate(acc, job_count=2, output_path=out, logger=self.logger)
        self.assertEqual(data["categories"]["invoices"]["failed"], 1)
        self.assertEqual(data["failed_count"], 1)
        self.assertEqual(data["discrepancy"], 0)

    def test_report_json_structure(self):
        acc = store.make_accumulator()
        store.update(acc, "invoices", 100)
        out = self._output_path()
        generate(acc, job_count=1, output_path=out, logger=self.logger)
        with open(out) as f:
            data = json.load(f)
        for key in ("run_id", "generated_at", "job_count", "total_processed",
                    "total_value", "failed_count", "discrepancy", "categories"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
