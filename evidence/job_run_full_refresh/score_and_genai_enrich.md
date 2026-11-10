# Task `score_and_genai_enrich` · notebook `04_score_and_genai_enrich` (executed, with outputs)

Executed by Lakeflow Job run 121437029937396 · task `score_and_genai_enrich` · task run 501525153117017 · result SUCCESS · 2026-11-10 00:10:05 UTC → 2026-11-10 00:14:07 UTC · source `src/notebooks/04_score_and_genai_enrich.py`

> Exported from the executed job run by `scripts/export_run_evidence.py`. Every output below is real.

# 04 · Batch scoring + GenAI case enrichment → serving-ready tables

1. Load the **`@champion`** model from Unity Catalog and score every payment (risk score, band, reason codes).
2. Build the **analyst alert queue** for the live window (model alerts not yet decided).
3. **GenAI** (`ai_query` → Claude on Foundation Model APIs): for each alert write an analyst summary,
   the likely scam typology, a **customer intervention script** (Consumer Duty-friendly, non-accusatory),
   and a recommended action. Analysts then spend their time talking to the customer, not reading raw fields.
4. Publish operational lookup tables (customer / payee / relationship profiles) that the app uses for
   **real-time scoring of a new payment** via Lakebase.

All outputs have Change Data Feed on, ready for Lakebase synced tables.

```python
%pip install -q lightgbm==4.6.0 mlflow==3.4.0
%restart_python
```
**Output:**

```text
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
databricks-agents 1.11.0 requires mlflow-skinny<4,>=3.11.1, but you have mlflow-skinny 3.4.0 which is incompatible.
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("fraud_schema", "northbridge_fraud")
dbutils.widgets.text("ml_schema", "northbridge_ml")
dbutils.widgets.text("batch_llm_endpoint", "databricks-claude-haiku-5-5")
dbutils.widgets.text("max_genai_alerts", "300")
CATALOG, FRAUD, ML, LLM = (dbutils.widgets.get(k) for k in ["catalog", "fraud_schema", "ml_schema", "batch_llm_endpoint"])
MAX_GENAI = int(dbutils.widgets.get("max_genai_alerts"))
MODEL_NAME = f"{CATALOG}.{ML}.app_scam_risk_model"
LIVE_START = "2026-11-01"           # analyst queue = last 7 days of payments

import json, mlflow, pandas as pd
from mlflow import MlflowClient
mlflow.set_registry_uri("databricks-uc")
mv = MlflowClient().get_model_version_by_alias(MODEL_NAME, "champion")
model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
meta = json.load(open(mlflow.artifacts.download_artifacts(f"models:/{MODEL_NAME}@champion") + "/artifacts/meta.json"))
print(f"champion = v{mv.version}; alert_threshold={meta['alert_threshold']:.4f} critical={meta['critical_threshold']:.4f}")
```
**Output:**

```text
champion = v3; alert_threshold=0.0969 critical=0.9922
```

## 1 · Score all payments

```python
cols = ["payment_id", "event_ts", "event_date", "customer_id", "payee_id", "amount_gbp", "rules_alert", "is_app_scam", "scam_type"]
from pyspark.sql import functions as F
pdf = (spark.table(f"{CATALOG}.{FRAUD}.gold_payment_features")
       .select(*cols, *[F.col(c).cast("double").alias(c) if c in meta["numeric"] + meta["boolean"] else F.col(c) for c in meta["features"] if c not in cols])
       .toPandas())
pred = model.predict(pdf[meta["features"]])
scores = pd.concat([pdf[cols].reset_index(drop=True), pred.reset_index(drop=True)], axis=1)
scores["model_alert"] = scores.risk_score >= meta["alert_threshold"]
scores["model_version"] = int(mv.version)
scores["scored_at"] = pd.Timestamp.utcnow().tz_localize(None)
sdf = spark.createDataFrame(scores)
sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{ML}.payment_risk_scores")
spark.sql(f"COMMENT ON TABLE {CATALOG}.{ML}.payment_risk_scores IS 'Every payment scored by the champion APP-scam model: risk_score, risk_band, reason_codes, model_alert vs legacy rules_alert, label (when known).'")
display(spark.sql(f"""
SELECT risk_band, count(*) AS payments, sum(is_app_scam) AS confirmed_scams, round(sum(CASE WHEN is_app_scam=1 THEN amount_gbp END),0) AS scam_value_gbp,
       sum(CASE WHEN rules_alert THEN 1 ELSE 0 END) AS rules_alerts
FROM {CATALOG}.{ML}.payment_risk_scores GROUP BY risk_band ORDER BY min(risk_score) DESC"""))
```
**Output:**

| risk_band | payments | confirmed_scams | scam_value_gbp | rules_alerts |
|---|---|---|---|---|
| CRITICAL | 915 | 825 | 5994808.0 | 307 |
| HIGH | 7355 | 1624 | 3460301.0 | 934 |
| MEDIUM | 5604 | 46 | 41169.0 | 528 |
| LOW | 1101095 | 155 | 139886.0 | 5077 |

## 2 · Alert queue for the live window (model alerts, highest risk first)

```python
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW live_alerts AS
SELECT
  concat('AL-', s.payment_id)          AS alert_id,
  s.payment_id, s.event_ts AS payment_ts, s.customer_id,
  c.full_name                          AS customer_display_name,     -- column-masked at source -> masked here
  c.age_band, c.vulnerability_flag, c.region, c.segment,
  f.amount_gbp, f.reference, f.channel, f.cop_result, f.is_new_payee, f.on_active_call,
  f.minutes_since_payee_added, f.payee_account_age_days, f.payee_distinct_senders_7d, f.amount_to_cust_avg_ratio,
  s.payee_id, py.payee_name, f.payee_bank_name, f.payee_bank_type,
  s.risk_score, s.risk_band, s.reason_codes, f.rules_alert AS legacy_rules_would_alert,
  s.model_version,
  s.event_ts + INTERVAL 4 HOURS        AS sla_due_ts
FROM {CATALOG}.{ML}.payment_risk_scores s
JOIN {CATALOG}.{FRAUD}.gold_payment_features f USING (payment_id)
LEFT JOIN {CATALOG}.{FRAUD}.silver_customers c ON s.customer_id = c.customer_id
LEFT JOIN {CATALOG}.{FRAUD}.silver_payees py ON s.payee_id = py.payee_id
WHERE s.event_date >= '{LIVE_START}' AND s.model_alert
""")
print("live model alerts:", spark.table("live_alerts").count())
```
**Output:**

```text
live model alerts: 572
```

## 3 · GenAI enrichment with `ai_query` (Claude via Foundation Model API)

```python
PROMPT = """You are a senior APP-scam (authorised push payment) investigator at a UK retail bank. A payment has been held by the fraud model.
Write for a fraud analyst who must phone the customer within 4 hours. Use UK English, GBP, plain language. Never accuse the customer.
Return ONLY a minified JSON object (no markdown) with exactly these keys:
 "suspected_scam_type": one of purchase|impersonation|investment|romance|advance_fee|invoice_redirection|unclear,
 "analyst_summary": 2 sentences on why this looks risky, citing the strongest signals,
 "customer_call_script": 3 short open questions the analyst should ask (Consumer Duty compliant, no leading questions), as one string with the questions separated by a vertical bar,
 "recommended_action": one of HOLD_AND_CALL|WARN_AND_RELEASE|RELEASE,
 "confidence": one of low|medium|high
Payment facts:
"""

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW genai_input AS
SELECT *, concat('{PROMPT.replace("'", "''")}',
  'amount GBP ', format_number(amount_gbp, 2), '; reference "', coalesce(reference, ''), '"; channel ', channel,
  '; Confirmation of Payee ', cop_result, '; new payee ', CAST(is_new_payee AS STRING),
  '; minutes since payee added ', coalesce(CAST(minutes_since_payee_added AS STRING), 'n/a'),
  '; receiving account age days ', coalesce(CAST(payee_account_age_days AS STRING), 'unknown'),
  '; receiving bank type ', payee_bank_type, '; distinct senders to this payee in 7d ', CAST(payee_distinct_senders_7d AS STRING),
  '; amount vs customer 90d average x', coalesce(CAST(amount_to_cust_avg_ratio AS STRING), 'n/a'),
  '; customer on active phone call ', CAST(on_active_call AS STRING), '; customer age band ', age_band,
  '; vulnerability flag ', CAST(vulnerability_flag AS STRING),
  '; model risk score ', CAST(round(risk_score, 3) AS STRING), ' (', risk_band, '); model reason codes ', reason_codes) AS prompt
FROM live_alerts
ORDER BY risk_score DESC
LIMIT {MAX_GENAI}
""")

enriched = spark.sql(f"""
WITH r AS (
  SELECT *, ai_query('{LLM}', prompt, failOnError => false, modelParameters => named_struct('max_tokens', 600, 'temperature', 0.1)) AS llm
  FROM genai_input
)
SELECT r.* EXCEPT (prompt, llm),
  from_json(regexp_extract(llm.result, '(?s)(\\\\{{.*\\\\}})', 1),
            'suspected_scam_type STRING, analyst_summary STRING, customer_call_script STRING, recommended_action STRING, confidence STRING') AS g,
  llm.errorMessage AS genai_error
FROM r
""").selectExpr("* EXCEPT (g)", "g.suspected_scam_type", "g.analyst_summary", "g.customer_call_script",
                "g.recommended_action", "g.confidence AS genai_confidence", f"'{LLM}' AS genai_model", "current_timestamp() AS enriched_at")
enriched.createOrReplaceTempView("enriched_alerts")
enriched_count = spark.table("enriched_alerts").count()
print("GenAI-enriched alerts:", enriched_count)
```
**Output:**

```text
GenAI-enriched alerts: 300
```

### Upsert into `alert_queue` (MERGE keeps CDF clean for the Lakebase triggered sync)

```python
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{ML}.alert_queue
COMMENT 'Analyst work queue: model-held payments in the live window, enriched by GenAI (summary, scam type, call script, action). Synced to Lakebase for the Scam Shield app.'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
AS SELECT * FROM enriched_alerts WHERE 1 = 0
""")
spark.sql(f"""
MERGE INTO {CATALOG}.{ML}.alert_queue t USING enriched_alerts s ON t.alert_id = s.alert_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""")
display(spark.sql(f"""
SELECT alert_id, customer_display_name, amount_gbp, risk_band, round(risk_score,3) AS risk, suspected_scam_type, recommended_action,
       legacy_rules_would_alert, left(analyst_summary, 160) AS analyst_summary_preview
FROM {CATALOG}.{ML}.alert_queue ORDER BY risk_score DESC LIMIT 10"""))
```
**Output:**

| alert_id | customer_display_name | amount_gbp | risk_band | risk | suspected_scam_type | recommended_action | legacy_rules_would_alert | analyst_summary_preview |
|---|---|---|---|---|---|---|---|---|
| AL-FP26001105668 | M**************n | 8551.7 | CRITICAL | 0.999 | None | None | False | None |
| AL-FP26001033467 | J********n | 11082.69 | CRITICAL | 0.999 | None | None | False | None |
| AL-FP26001101848 | W*************t | 18042.31 | CRITICAL | 0.999 | None | None | True | None |
| AL-FP26001055178 | O**********l | 8769.37 | CRITICAL | 0.999 | None | None | False | None |
| AL-FP26001055177 | M**************n | 6719.19 | CRITICAL | 0.999 | None | None | True | None |
| AL-FP26001042663 | F************n | 9221.49 | CRITICAL | 0.999 | None | None | False | None |
| AL-FP26001080490 | L*******r | 8747.14 | CRITICAL | 0.999 | None | None | False | None |
| AL-FP26001100796 | N*********n | 3883.49 | CRITICAL | 0.999 | None | None | False | None |
| AL-FP26001098751 | O**********l | 10648.52 | CRITICAL | 0.998 | None | None | False | None |
| AL-FP26001043091 | F************n | 10848.81 | CRITICAL | 0.998 | None | None | True | None |

```python
display(spark.sql(f"""
SELECT suspected_scam_type, recommended_action, count(*) AS alerts, round(avg(risk_score),3) AS avg_risk,
       sum(CASE WHEN genai_error IS NOT NULL AND genai_error <> '' THEN 1 ELSE 0 END) AS genai_errors
FROM {CATALOG}.{ML}.alert_queue GROUP BY ALL ORDER BY alerts DESC"""))
```
**Output:**

| suspected_scam_type | recommended_action | alerts | avg_risk | genai_errors |
|---|---|---|---|---|
| None | None | 300 | 0.9 | 300 |

### One full GenAI case note (verbatim model output)

```python
for r in spark.sql(f"SELECT alert_id, amount_gbp, reason_codes, suspected_scam_type, analyst_summary, customer_call_script, recommended_action FROM {CATALOG}.{ML}.alert_queue ORDER BY risk_score DESC LIMIT 2").collect():
    print(json.dumps(r.asDict(), indent=2, default=str)); print("-" * 100)
```
**Output:**

```text
{
  "alert_id": "AL-FP26001105668",
  "amount_gbp": 8551.7,
  "reason_codes": "[\"Payment made minutes after the payee was created\", \"High payment value\", \"No payment history with this payee\"]",
  "suspected_scam_type": null,
  "analyst_summary": null,
  "customer_call_script": null,
  "recommended_action": null
}
----------------------------------------------------------------------------------------------------
{
  "alert_id": "AL-FP26001033467",
  "amount_gbp": 11082.69,
  "reason_codes": "[\"Payment made minutes after the payee was created\", \"High payment value\", \"No payment history with this payee\"]",
  "suspected_scam_type": null,
  "analyst_summary": null,
  "customer_call_script": null,
  "recommended_action": null
}
----------------------------------------------------------------------------------------------------
```

## 4 · Operational profiles for real-time scoring (synced to Lakebase)

```python
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{ML}.customer_profile
COMMENT 'Per-customer behavioural baseline as of the latest data (synced to Lakebase for <10ms lookups by the real-time payment check).'
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
WITH last AS (SELECT max(event_ts) AS as_of FROM {CATALOG}.{FRAUD}.gold_payment_features)
SELECT c.customer_id, c.full_name AS customer_display_name, c.age_years, c.age_band, c.vulnerability_flag, c.tenure_months,
       c.digital_active, c.segment, c.region,
       round(avg(f.amount_gbp), 2) AS cust_avg_amount_90d, round(max(f.amount_gbp), 2) AS cust_max_amount_90d, count(f.payment_id) AS cust_payments_90d,
       sum(CASE WHEN f.event_ts >= last.as_of - INTERVAL 24 HOURS THEN 1 ELSE 0 END) AS cust_payments_24h,
       sum(CASE WHEN f.event_ts >= last.as_of - INTERVAL 24 HOURS AND f.is_new_payee THEN 1 ELSE 0 END) AS cust_new_payee_payments_24h,
       round(sum(CASE WHEN f.event_ts >= last.as_of - INTERVAL 24 HOURS THEN f.amount_gbp ELSE 0 END), 2) AS cust_value_24h,
       sum(f.is_app_scam) AS prior_confirmed_scams, max(last.as_of) AS as_of_ts
FROM {CATALOG}.{FRAUD}.silver_customers c
CROSS JOIN last
LEFT JOIN {CATALOG}.{FRAUD}.gold_payment_features f ON f.customer_id = c.customer_id
GROUP BY ALL
""")
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{ML}.payee_profile
COMMENT 'Per-receiving-account risk context (account age, 7-day distinct senders, watchlist flag) for real-time scoring. Synced to Lakebase.'
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
WITH last AS (SELECT max(event_ts) AS as_of FROM {CATALOG}.{FRAUD}.gold_payment_features)
SELECT p.payee_id, p.payee_name, p.payee_category, p.payee_bank_name, p.payee_bank_type, p.payee_account_opened_date, p.intel_available,
       count(DISTINCT CASE WHEN f.event_ts >= last.as_of - INTERVAL 7 DAYS THEN f.customer_id END) AS payee_distinct_senders_7d,
       sum(CASE WHEN f.event_ts >= last.as_of - INTERVAL 7 DAYS THEN 1 ELSE 0 END) AS payee_inbound_payments_7d,
       (m.payee_id IS NOT NULL) AS on_mule_watchlist
FROM {CATALOG}.{FRAUD}.silver_payees p CROSS JOIN last
LEFT JOIN {CATALOG}.{FRAUD}.gold_payment_features f ON f.payee_id = p.payee_id
LEFT JOIN {CATALOG}.{FRAUD}.gold_mule_watchlist m ON m.payee_id = p.payee_id
GROUP BY ALL
""")
spark.sql(f"""
CREATE OR REPLACE TABLE {CATALOG}.{ML}.customer_payee_history
COMMENT 'Customer -> payee relationship (prior payments count, first/last paid). Lets the app compute is_new_payee / prior_payments_to_payee in real time.'
TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
SELECT concat(customer_id, ':', payee_id) AS relationship_id, customer_id, payee_id, count(*) AS prior_payments,
       min(event_ts) AS first_paid_ts, max(event_ts) AS last_paid_ts
FROM {CATALOG}.{FRAUD}.gold_payment_features GROUP BY customer_id, payee_id
""")
counts = {t: spark.table(f"{CATALOG}.{ML}.{t}").count() for t in ["payment_risk_scores", "alert_queue", "customer_profile", "payee_profile", "customer_payee_history"]}
print(json.dumps(counts, indent=2))
dbutils.notebook.exit(json.dumps({"model_version": int(mv.version), "genai_enriched": enriched_count, **counts}))
```

## Logged notebook exit value (`dbutils.notebook.exit`, from the Jobs API)

```json
{
  "model_version": 3,
  "genai_enriched": 300,
  "payment_risk_scores": 1114969,
  "alert_queue": 300,
  "customer_profile": 50000,
  "payee_profile": 121100,
  "customer_payee_history": 318385
}
```