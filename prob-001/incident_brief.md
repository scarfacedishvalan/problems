# Incident: Nightly Batch Report Discrepancy

**Severity:** P2
**Opened:** 2026-06-19 22:41 UTC
**Reported by:** Finance Operations (automated reconciliation)
**Run ID:** run-1719792000

---

## Alert

> [finance-reconciliation] NightProc batch run-1719792000 total mismatch.
> Expected >=275,000. Actual: 233,576. Unaccounted jobs: 17.
> No errors detected. Batch marked complete.

---

## What Finance sees

The nightly batch report (`report.json`) shows fewer successfully processed jobs and a
lower total value than their internal ledger. All jobs appear to have completed: no
failed jobs appear in the report and no error alerts fired during the run.

This pattern has not been seen before. The previous night's run was clean.

---

## Reproduction

The batch was invoked as:

```bash
python run_batch.py jobs/nightly_full.json --threads 8
```

Logs are written to `logs/nightproc.log`.

---

## Available signals

| Signal | Location |
|---|---|
| Structured run log | `logs/nightproc.log` |
| Disputed report | `report.json` |
| Job input | `jobs/nightly_full.json` |
| Source | `nightproc/` |

---

## Notes

- Finance confirmed the input file is unchanged from prior nights.
- The report `discrepancy` field is non-zero. Expected value is 0.
- Re-running the batch produces a different discrepancy count each time.
