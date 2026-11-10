#!/usr/bin/env python3
"""Export the Lakeflow SDP pipeline's event log (the pipeline's own run log) as Markdown text evidence.

Usage: python3 scripts/export_pipeline_log.py [--profile P] [--warehouse ID] [--out evidence/pipeline_event_log.md]
"""
import argparse
import json
import pathlib
import subprocess
from datetime import datetime, timezone


def cli(args, profile):
    r = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"], capture_output=True, text=True, check=True)
    return json.loads(r.stdout, strict=False)


def q(sql, a):
    return cli(["experimental", "aitools", "tools", "query", sql, "--warehouse", a.warehouse], a.profile)


def md(rows, cols=None):
    if not rows:
        return "_(no rows)_"
    cols = cols or list(rows[0].keys())
    f = lambda v: str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")[:260]  # noqa: E731
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(f(r.get(c)) for c in cols) + " |" for r in rows])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fevm-serverless-stable-my49a8")
    ap.add_argument("--warehouse", default="1035b8c40230fe40")
    ap.add_argument("--out", default="evidence/pipeline_event_log.md")
    a = ap.parse_args()
    p = cli(["pipelines", "list-pipelines", "--filter", "name LIKE 'northbridge-app-fraud-medallion'"], a.profile)[0]
    pid = p["pipeline_id"]
    ev = f"event_log('{pid}')"
    updates = q(f"""
      SELECT origin.update_id AS update_id, min(timestamp) AS started, max(timestamp) AS finished,
             max_by(details:update_progress.state, timestamp) AS final_state,
             max(CAST(details:create_update.full_refresh AS BOOLEAN)) AS full_refresh,
             max(details:create_update.cause) AS cause
      FROM {ev} WHERE origin.update_id IS NOT NULL GROUP BY 1 ORDER BY started""", a)
    fr = max((i for i, u in enumerate(updates) if str(u.get("full_refresh")).lower() == "true"), default=len(updates) - 2)
    last_two = [updates[fr]["update_id"]] + ([updates[fr + 1]["update_id"]] if fr + 1 < len(updates) else [])
    sections = []
    for uid in last_two:
        flows = q(f"""
          SELECT element_at(split(origin.flow_name, '[.]'), -1) AS flow,
                 max_by(CAST(details:flow_progress.status AS STRING), timestamp) FILTER (WHERE CAST(details:flow_progress.status AS STRING) <> '') AS final_status,
                 sum(CAST(details:flow_progress.metrics.num_output_rows AS BIGINT)) AS rows_written,
                 sum(CAST(details:flow_progress.metrics.num_upserted_rows AS BIGINT)) AS rows_upserted_auto_cdc
          FROM {ev} WHERE event_type = 'flow_progress' AND origin.update_id = '{uid}' AND origin.flow_name LIKE '%northbridge%'
          GROUP BY 1 ORDER BY 1""", a)
        dq = q(f"""
          WITH e AS (SELECT explode(from_json(details:flow_progress.data_quality.expectations,
                       'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS x
                     FROM {ev} WHERE event_type = 'flow_progress' AND origin.update_id = '{uid}'
                       AND details:flow_progress.data_quality.expectations IS NOT NULL)
          SELECT element_at(split(x.dataset, '[.]'), -1) AS dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed
          FROM e GROUP BY 1, 2 ORDER BY 1, 2""", a)
        drops = q(f"""
          SELECT sum(CAST(details:flow_progress.data_quality.dropped_records AS BIGINT)) AS dropped_records
          FROM {ev} WHERE event_type = 'flow_progress' AND origin.update_id = '{uid}'""", a)
        log = q(f"""
          SELECT timestamp, event_type, level, coalesce(origin.flow_name, '') AS flow, left(message, 200) AS message
          FROM {ev} WHERE origin.update_id = '{uid}' AND event_type IN ('create_update', 'update_progress', 'flow_progress', 'planning_information')
            AND (event_type <> 'flow_progress' OR details:flow_progress.status IN ('COMPLETED', 'FAILED', 'STARTING'))
          ORDER BY timestamp LIMIT 80""", a)
        u = next(x for x in updates if x["update_id"] == uid)
        sections += [f"## Update `{uid}` · {u['final_state']} · full_refresh={u['full_refresh']} · {u['started']} → {u['finished']}", "",
                     "### Flows (final status and rows written in this update)", "", md(flows), "",
                     "### Data-quality expectations in this update", "", md(dq), "",
                     f"Rows dropped by `ON VIOLATION DROP ROW` expectations in this update: **{drops[0].get('dropped_records') if drops else 'n/a'}**", "",
                     "### Event log (chronological)", "", md(log), ""]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = ["# Lakeflow pipeline run log: `northbridge-app-fraud-medallion`", "",
           f"Pipeline id `{pid}` · serverless · Photon · catalog `serverless_stable_my49a8_catalog`, schema `northbridge_fraud` · exported {now} from the pipeline **event log** "
           f"(`event_log('{pid}')`, queried on SQL warehouse `{a.warehouse}`) by `scripts/export_pipeline_log.py`.", "",
           "## All pipeline updates", "", md(updates), "",
           "Detailed below: the latest **full refresh** (initial load of 89 days) and the **incremental** update that followed it (business day 2026-11-08 arriving). "
           "Later updates are job re-runs with no new files (Auto Loader reads nothing new).", ""]
    pathlib.Path(a.out).write_text("\n".join(out + sections))
    print("wrote", a.out, "updates:", len(updates))


if __name__ == "__main__":
    main()
