#!/usr/bin/env python3
"""Run real queries against the deployed build and commit the results as Markdown (text evidence).

Usage: python3 scripts/collect_platform_evidence.py [--profile P] [--warehouse ID] [--out evidence/platform_queries.md]
"""
import argparse
import json
import pathlib
import subprocess
from datetime import datetime, timezone

C = "serverless_stable_my49a8_catalog"


def q(sql, profile, wh):
    r = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", sql, "--warehouse", wh, "--profile", profile, "-o", "json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip()[:800]
    try:
        return json.loads(r.stdout), None
    except json.JSONDecodeError:
        return None, r.stdout[:800]


def md(rows, max_rows=30):
    if not rows:
        return "_(no rows)_"
    cols = list(rows[0].keys())
    f = lambda v: str(v).replace("|", "\\|").replace("\n", " ")[:200]  # noqa: E731
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(f(r.get(c)) for c in cols) + " |" for r in rows[:max_rows]]
    if len(rows) > max_rows:
        out.append(f"\n_… {len(rows) - max_rows} more rows_")
    return "\n".join(out)


def pipeline_id(profile):
    r = subprocess.run(["databricks", "pipelines", "list-pipelines", "--filter", "name LIKE 'northbridge-app-fraud-medallion'", "--profile", profile, "-o", "json"],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)[0]["pipeline_id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fevm-serverless-stable-my49a8")
    ap.add_argument("--warehouse", default="1035b8c40230fe40")
    ap.add_argument("--out", default="evidence/platform_queries.md")
    a = ap.parse_args()
    pid = pipeline_id(a.profile)
    F, M, O, H = f"{C}.northbridge_fraud", f"{C}.northbridge_ml", f"{C}.northbridge_ops", f"{C}.northbridge_ops_history"
    checks = [
        ("1. Lakeflow: rows per medallion table", f"""
SELECT 'bronze_payments' AS table_name, count(*) AS rows FROM {F}.bronze_payments UNION ALL
SELECT 'silver_payments_validated', count(*) FROM {F}.silver_payments_validated UNION ALL
SELECT 'silver_payments_quarantine', count(*) FROM {F}.silver_payments_quarantine UNION ALL
SELECT 'silver_payments (AUTO CDC de-duplicated)', count(*) FROM {F}.silver_payments UNION ALL
SELECT 'silver_customers', count(*) FROM {F}.silver_customers UNION ALL
SELECT 'silver_payees', count(*) FROM {F}.silver_payees UNION ALL
SELECT 'silver_scam_claims', count(*) FROM {F}.silver_scam_claims UNION ALL
SELECT 'gold_payment_features', count(*) FROM {F}.gold_payment_features UNION ALL
SELECT 'gold_daily_fraud_kpis', count(*) FROM {F}.gold_daily_fraud_kpis UNION ALL
SELECT 'gold_mule_watchlist', count(*) FROM {F}.gold_mule_watchlist"""),
        ("2. Lakeflow: Auto Loader files ingested per source", f"""
SELECT regexp_extract(_source_file, 'landing/([a-z_]+)/', 1) AS source, count(DISTINCT _source_file) AS files, count(*) AS rows
FROM {F}.bronze_payments GROUP BY 1 UNION ALL
SELECT 'scam_claims', count(DISTINCT _source_file), count(*) FROM {F}.bronze_scam_claims"""),
        ("3. Lakeflow: data-quality expectations (pipeline event log, latest update)", f"""
WITH e AS (
  SELECT origin.flow_name AS flow, explode(from_json(details:flow_progress.data_quality.expectations,
         'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS x, timestamp
  FROM event_log('{pid}') WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL)
SELECT x.dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed
FROM e GROUP BY 1, 2 ORDER BY 1, 2"""),
        ("4. Lakeflow: quarantine reasons", f"SELECT quarantine_reason, count(*) AS rows FROM {F}.silver_payments_quarantine GROUP BY 1 ORDER BY 2 DESC"),
        ("5. Lakeflow: pipeline updates (event log)", f"""
SELECT timestamp, details:update_progress.state AS state, origin.update_id
FROM event_log('{pid}') WHERE event_type = 'update_progress' AND details:update_progress.state IN ('COMPLETED', 'FAILED') ORDER BY timestamp DESC LIMIT 10"""),
        ("6. Unity Catalog: column masks bound to tables", f"SELECT table_name, column_name, mask_name FROM {C}.information_schema.column_masks WHERE table_schema = 'northbridge_fraud' ORDER BY 1, 2"),
        ("7. Unity Catalog: what a non-PII reader sees (masked)", f"SELECT current_user() AS evaluated_as, customer_id, full_name, date_of_birth, email, postcode, postcode_district, age_band FROM {F}.silver_customers ORDER BY customer_id LIMIT 5"),
        ("8. Unity Catalog: governed tags", f"""
SELECT 'table' AS level, table_name AS object, tag_name, tag_value FROM {C}.information_schema.table_tags WHERE schema_name = 'northbridge_fraud' UNION ALL
SELECT 'column', concat(table_name, '.', column_name), tag_name, tag_value FROM {C}.information_schema.column_tags WHERE schema_name = 'northbridge_fraud'
ORDER BY 1 DESC, 2, 3"""),
        ("9. Unity Catalog: lineage captured (system.access.table_lineage)", f"""
SELECT DISTINCT source_table_full_name, target_table_full_name FROM system.access.table_lineage
WHERE target_table_catalog = '{C}' AND target_table_schema LIKE 'northbridge%' AND source_table_full_name IS NOT NULL
ORDER BY 2, 1"""),
        ("10. Unity Catalog: schema grants", f"SELECT grantee, schema_name, privilege_type FROM {C}.information_schema.schema_privileges WHERE schema_name LIKE 'northbridge%' ORDER BY 2, 1, 3"),
        ("11. ML: hold-out evaluation, rules vs model at the same alert budget", f"SELECT * FROM {M}.model_evaluation"),
        ("12. ML: value recall by scam typology", f"SELECT * FROM {M}.model_recall_by_scam_type ORDER BY scam_value_gbp DESC"),
        ("13. ML: risk-band distribution over all scored payments", f"""
SELECT risk_band, count(*) AS payments, sum(is_app_scam) AS confirmed_scams, round(sum(CASE WHEN is_app_scam = 1 THEN amount_gbp END), 0) AS scam_value_gbp,
       sum(CASE WHEN rules_alert THEN 1 ELSE 0 END) AS rules_alerts, max(model_version) AS model_version
FROM {M}.payment_risk_scores GROUP BY 1 ORDER BY min(risk_score) DESC"""),
        ("14. GenAI: alert queue enrichment summary (ai_query, Claude)", f"""
SELECT suspected_scam_type, recommended_action, count(*) AS alerts, round(avg(risk_score), 3) AS avg_risk,
       sum(CASE WHEN legacy_rules_would_alert THEN 0 ELSE 1 END) AS missed_by_rules, max(genai_model) AS model
FROM {M}.alert_queue GROUP BY 1, 2 ORDER BY 3 DESC"""),
        ("15. GenAI: three verbatim case notes", f"""
SELECT alert_id, round(amount_gbp, 2) AS amount_gbp, reference, reason_codes, suspected_scam_type, analyst_summary, customer_call_script, recommended_action
FROM {M}.alert_queue ORDER BY risk_score DESC LIMIT 3"""),
        ("16. Semantic layer: metric view query (MEASURE)", f"""
SELECT `Scam Type`, MEASURE(`Confirmed Scam Value GBP`) AS scam_value_gbp, MEASURE(`Rules Value Recall`) AS rules_value_recall,
       MEASURE(`Model Value Recall`) AS model_value_recall, MEASURE(`Net Reimbursement Cost GBP`) AS net_cost_gbp
FROM {M}.app_scam_metrics WHERE `Payment Date` BETWEEN '2026-10-10' AND '2026-10-29' AND `Scam Type` <> 'not a scam' GROUP BY ALL ORDER BY 2 DESC"""),
        ("17. Business case table", f"SELECT sort_order, metric, round(value, 4) AS value, unit, basis FROM {M}.business_case ORDER BY sort_order"),
        ("18. Lakebase synced tables registered in UC", f"SELECT table_name, table_type, comment FROM {C}.information_schema.tables WHERE table_schema = 'northbridge_ops' ORDER BY 1"),
        ("19. Lakehouse Sync: analyst decisions flowing back from Lakebase to UC", f"""
SELECT _pg_change_type, decision, count(*) AS rows, round(sum(amount_protected_gbp), 2) AS amount_protected_gbp, max(_timestamp) AS last_change
FROM {H}.lb_case_decisions_history GROUP BY 1, 2 ORDER BY 1, 2"""),
        ("20. Lakehouse Sync: live payment checks logged by the app", f"""
SELECT risk_band, action, count(*) AS checks, round(avg(lookup_ms), 1) AS avg_lakebase_lookup_ms, round(avg(scoring_ms), 1) AS avg_model_serving_ms
FROM {H}.lb_payment_checks_history WHERE _pg_change_type = 'insert' GROUP BY 1, 2 ORDER BY 1"""),
        ("21. Model Serving: inference table (AI Gateway) request log", f"""
SELECT date(request_time) AS day, count(*) AS requests, round(avg(execution_duration_ms), 1) AS avg_exec_ms, max(served_entity_id) IS NOT NULL AS logged
FROM {M}.scam_risk_serving_payload GROUP BY 1 ORDER BY 1 DESC LIMIT 5"""),
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# Platform evidence: live query results", "", f"Captured {now} against workspace `{a.profile}` via `databricks experimental aitools tools query` (SQL warehouse `{a.warehouse}`).",
           f"Pipeline id: `{pid}`. Every block below is the real query and its real result.", ""]
    for title, sql in checks:
        rows, err = q(sql.strip(), a.profile, a.warehouse)
        out += [f"## {title}", "", "```sql", sql.strip(), "```", "", md(rows) if err is None else f"> query error: `{err}`", ""]
        print(title, "OK" if err is None else "ERR")
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text("\n".join(out))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
