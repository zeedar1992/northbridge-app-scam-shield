# Incremental run: the next business day arrives

**Scenario:** the payments hub drops `payments_2026-11-08.json` (and the day's claims file). The same Lakeflow Job is re-run with
`databricks bundle run northbridge_journey --params through_date=2026-11-08` (job run **590537578235560**, all tasks SUCCESS, see [`job_run_incremental/run_summary.md`](job_run_incremental/run_summary.md)).

## Before (end of the full-refresh run 121437029937396)
```json
{"files":"89","max_ts":"2026-11-07T23:59:58.000Z","rows":"1120109"}
```

## Auto Loader ingested only the new file
Bronze rows grouped by ingestion batch (`_ingested_at` is stamped by the bronze streaming table):

| ingestion batch (UTC) | files | rows | first file day | last file day |
|---|---|---|---|---|
| 2026-11-09T23:30:00.000Z | 89 | 1120109 | 2026-08-11 | 2026-11-07 |
| 2026-11-10T00:24:00.000Z | 1 | 12676 | 2026-11-08 | 2026-11-08 |

The second batch is exactly **one file / 12,676 rows**. The 89 historical files were not re-read, because Auto Loader checkpoints which files it has processed.

## Downstream stages picked up the new day
`gold_daily_fraud_kpis` (materialized view, refreshed by the same pipeline update):

| event_date | payments | rules_alerts | confirmed_scam_payments |
|---|---|---|---|
| 2026-11-06 | 12463 | 87 | 11 |
| 2026-11-07 | 12601 | 95 | 3 |
| 2026-11-08 | 12619 | 91 | 1 |

> 2026-11-08 has almost no confirmed scams yet. That's **label lag**: claims arrive days later, which is why evaluation uses a mature test window (10–29 Oct) and the newest days only feed the live alert queue.

Then the same run retrained the model (registered **v4**, alias `@champion` moved), deployed v4 to Model Serving, re-scored, MERGEd the GenAI-enriched alert queue, and refreshed the Lakebase synced tables (`alert_queue` TRIGGERED from Change Data Feed). The scoring step was repaired once in this run after a GenAI fix (Claude 5.5 rejects `temperature` and needs a larger `max_tokens`). See `docs/ai-assisted-build.md`.
