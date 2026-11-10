# Task `semantic_layer_business_case` · notebook `07_semantic_layer_and_business_case` (executed, with outputs)

Executed by Lakeflow Job run 121437029937396 · task `semantic_layer_business_case` · task run 137984998434180 · result SUCCESS · 2026-11-10 00:14:07 UTC → 2026-11-10 00:14:23 UTC · source `src/notebooks/07_semantic_layer_and_business_case.py`

> Exported from the executed job run by `scripts/export_run_evidence.py`. Every output below is real.

# 07 · Governed semantic layer (UC metric view) + quantified business case

**Metric view** `northbridge_ml.app_scam_metrics` – one governed definition of every KPI the Head of Fraud,
the Genie Agent and the app use (scam value caught, precision, reimbursement cost …). No more "which number is right?".

**Business case** `northbridge_ml.business_case` – the synthetic sample is deliberately *scam-enriched* (≈0.3% of payments)
so the model has enough positives to learn from. We therefore do **not** extrapolate synthetic £ totals. Instead we take the
measured *rates* from the hold-out test (value recall and precision of rules vs model at the same alert budget) and apply them to
Northbridge's real-world baseline derived from published UK figures. Every assumption is a row in the table.

```python
dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("fraud_schema", "northbridge_fraud")
dbutils.widgets.text("ml_schema", "northbridge_ml")
CATALOG, FRAUD, ML = (dbutils.widgets.get(k) for k in ["catalog", "fraud_schema", "ml_schema"])
```

```python
spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG}.{ML}.app_scam_metrics
WITH METRICS
LANGUAGE YAML
COMMENT 'Governed APP-scam KPIs for Northbridge Bank: volumes, confirmed scam losses, rules vs ML model interception, precision and PSR reimbursement cost.'
AS $$
version: 1.1
source: |
  SELECT f.*, s.risk_score, s.risk_band, s.model_alert, s.model_version
  FROM {CATALOG}.{FRAUD}.gold_payment_features f
  JOIN {CATALOG}.{ML}.payment_risk_scores s USING (payment_id)
dimensions:
  - name: Payment Date
    expr: event_date
  - name: Payment Month
    expr: DATE_TRUNC('MONTH', event_date)
  - name: Scam Type
    expr: coalesce(scam_type, 'not a scam')
    comment: PSR / UK Finance APP scam typology from upheld claims
  - name: Channel
    expr: channel
  - name: Receiving Bank Type
    expr: payee_bank_type
  - name: Receiving Bank
    expr: payee_bank_name
  - name: Customer Age Band
    expr: age_band
  - name: Region
    expr: region
  - name: Vulnerable Customer
    expr: vulnerability_flag
  - name: New Payee
    expr: is_new_payee
  - name: Model Risk Band
    expr: risk_band
measures:
  - name: Payments
    expr: COUNT(1)
  - name: Payment Value GBP
    expr: SUM(amount_gbp)
  - name: Confirmed Scam Payments
    expr: SUM(is_app_scam)
  - name: Confirmed Scam Value GBP
    expr: SUM(CASE WHEN is_app_scam = 1 THEN amount_gbp ELSE 0 END)
    synonyms: [scam losses, fraud losses, APP losses]
  - name: Rules Alerts
    expr: COUNT(1) FILTER (WHERE rules_alert)
  - name: Model Alerts
    expr: COUNT(1) FILTER (WHERE model_alert)
  - name: Scam Value Caught By Rules GBP
    expr: SUM(CASE WHEN is_app_scam = 1 AND rules_alert THEN amount_gbp ELSE 0 END)
  - name: Scam Value Caught By Model GBP
    expr: SUM(CASE WHEN is_app_scam = 1 AND model_alert THEN amount_gbp ELSE 0 END)
  - name: Rules Value Recall
    expr: MEASURE(`Scam Value Caught By Rules GBP`) / NULLIF(MEASURE(`Confirmed Scam Value GBP`), 0)
    comment: Share of confirmed scam value the legacy rules engine would have held
  - name: Model Value Recall
    expr: MEASURE(`Scam Value Caught By Model GBP`) / NULLIF(MEASURE(`Confirmed Scam Value GBP`), 0)
    comment: Share of confirmed scam value the ML model would have held
  - name: Rules Precision
    expr: (COUNT(1) FILTER (WHERE rules_alert AND is_app_scam = 1)) / NULLIF(MEASURE(`Rules Alerts`), 0)
  - name: Model Precision
    expr: (COUNT(1) FILTER (WHERE model_alert AND is_app_scam = 1)) / NULLIF(MEASURE(`Model Alerts`), 0)
  - name: Reimbursed GBP
    expr: SUM(reimbursed_amount_gbp)
    comment: Paid to victims under the PSR reimbursement requirement (cap GBP 85,000 per claim)
  - name: Net Reimbursement Cost GBP
    expr: SUM(northbridge_net_cost_gbp)
    comment: Northbridge share after 50 percent contribution from the receiving PSP
    synonyms: [reimbursement liability, net cost]
$$
""")
display(spark.sql(f"""
SELECT `Scam Type`, MEASURE(`Confirmed Scam Value GBP`) AS scam_value, MEASURE(`Rules Value Recall`) AS rules_recall,
       MEASURE(`Model Value Recall`) AS model_recall, MEASURE(`Net Reimbursement Cost GBP`) AS net_cost
FROM {CATALOG}.{ML}.app_scam_metrics
WHERE `Payment Date` BETWEEN '2026-10-10' AND '2026-10-29' AND `Scam Type` <> 'not a scam'
GROUP BY ALL ORDER BY scam_value DESC"""))
```
**Output:**

| Scam Type | scam_value | rules_recall | model_recall | net_cost |
|---|---|---|---|---|
| investment | 1412132.6099999999 | 0.6967656953974031 | 0.9889345732197204 | 692194.41 |
| romance | 364199.37999999983 | 0.10461846475411359 | 0.9944401607712786 | 175327.24999999994 |
| impersonation | 327567.8999999999 | 0.8335958743210189 | 0.933728762800018 | 159843.56999999995 |
| purchase | 135690.11000000002 | 0.08619500713795575 | 0.7313275079517584 | 67004.37999999996 |
| invoice_redirection | 94032.15000000001 | 0.7787093031479125 | 0.7382073046293208 | 45248.62 |
| advance_fee | 19595.89 | 0.0 | 0.8250617859153119 | 9728.46 |

## Business case (annual, Northbridge Bank)

```python
import pandas as pd
ev = {r.approach: r for r in spark.table(f"{CATALOG}.{ML}.model_evaluation").collect()}
R, M = ev["rules_engine"], ev["ml_model_same_budget"]

# ---- published facts
UK_APP_LOSSES_2024 = 450_700_000      # UK Finance Annual Fraud Report 2025 (2024 APP losses)
PSR_REIMBURSED_SHARE = 0.88           # PSR, Oct-2025 one-year update: 88% of reimbursable APP losses returned (by value)
RECEIVING_PSP_SHARE = 0.50            # PSR reimbursement requirement: 50:50 sending / receiving PSP
# ---- Northbridge assumptions (fictional bank, to be validated in discovery)
MARKET_SHARE = 0.026                  # 2.1M of ~80M UK personal current accounts
INTERVENTION_SUCCESS = 0.60           # share of held scam value actually stopped after analyst call / warning
HOLDS_PER_DAY = 1_200                 # manual payment holds Northbridge fraud ops works per day (same budget both scenarios)
MINUTES_PER_CASE_TODAY = 11.0         # assemble evidence + decide + call
MINUTES_PER_CASE_GENAI = 7.0          # with GenAI case note + call script (pilot target)
LOADED_COST_PER_HOUR = 38.0           # fully loaded fraud analyst cost, GBP
PLATFORM_RUN_COST = 180_000           # annual Databricks + ops run cost estimate (pipeline, Lakebase, serving, FMAPI, app)

nb_losses_today = UK_APP_LOSSES_2024 * MARKET_SHARE                      # scam value that gets through today
attempted = nb_losses_today / (1 - R.value_recall * INTERVENTION_SUCCESS) # implied attempted scam value
losses_with_model = attempted * (1 - M.value_recall * INTERVENTION_SUCCESS)
customer_losses_prevented = nb_losses_today - losses_with_model
net_saving = customer_losses_prevented * PSR_REIMBURSED_SHARE * (1 - RECEIVING_PSP_SHARE)
analyst_hours = HOLDS_PER_DAY * 365 * (MINUTES_PER_CASE_TODAY - MINUTES_PER_CASE_GENAI) / 60
analyst_value = analyst_hours * LOADED_COST_PER_HOUR
fp_per_scam_rules = (1 - R.precision) / max(R.precision, 1e-9)
fp_per_scam_model = (1 - M.precision) / max(M.precision, 1e-9)
total_value = net_saving + analyst_value

rows = [
 (1,  "rules_value_recall",        "Scam value held by today's rules (hold-out test)", R.value_recall, "pct", "Measured: model_evaluation, same alert budget", False),
 (2,  "model_value_recall",        "Scam value held by ML model (hold-out test)",     M.value_recall, "pct", "Measured: model_evaluation, same alert budget", False),
 (3,  "nb_losses_today",           "Northbridge APP scam losses today (per year)",    nb_losses_today, "GBP", f"UK Finance 2024 APP losses GBP 450.7m x {MARKET_SHARE:.1%} PCA share (assumption)", False),
 (4,  "attempted_scam_value",      "Implied attempted scam value (per year)",          attempted, "GBP", f"losses / (1 - rules recall x {INTERVENTION_SUCCESS:.0%} intervention success)", False),
 (5,  "customer_losses_prevented", "Customer losses prevented (per year)",             customer_losses_prevented, "GBP", "attempted x (model recall - rules recall) x intervention success", False),
 (6,  "annual_net_saving_gbp",     "Northbridge net reimbursement cost avoided",       net_saving, "GBP", f"prevented x {PSR_REIMBURSED_SHARE:.0%} reimbursed (PSR) x 50% after receiving-PSP share", False),
 (7,  "analyst_hours_saved",       "Analyst hours released (per year)",                analyst_hours, "hours", f"{HOLDS_PER_DAY:,} holds/day x ({MINUTES_PER_CASE_TODAY:.0f} -> {MINUTES_PER_CASE_GENAI:.0f} min) with GenAI case notes", False),
 (8,  "analyst_value_gbp",         "Value of analyst capacity released",               analyst_value, "GBP", f"hours x GBP {LOADED_COST_PER_HOUR:.0f}/h loaded cost (redeploy to complex cases)", False),
 (9,  "genuine_holds_per_scam_rules", "Genuine customers held per scam caught: rules", fp_per_scam_rules, "ratio", "Measured: 1/precision - 1", False),
 (10, "genuine_holds_per_scam_model", "Genuine customers held per scam caught: model", fp_per_scam_model, "ratio", "Measured: Consumer Duty friction indicator", False),
 (11, "platform_run_cost",         "Platform run cost (per year)",                    -PLATFORM_RUN_COST, "GBP", "Estimate: serverless pipeline + Lakebase + serving + FMAPI + app", False),
 (12, "total_annual_value",        "Net annual value to Northbridge",                 total_value - PLATFORM_RUN_COST, "GBP", "net reimbursement avoided + analyst capacity - run cost", True),
]
bc = pd.DataFrame(rows, columns=["sort_order", "metric_key", "metric", "value", "unit", "basis", "is_total"])
bc["value"] = bc["value"].astype(float).round(4)
spark.createDataFrame(bc).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{ML}.business_case")
spark.sql(f"COMMENT ON TABLE {CATALOG}.{ML}.business_case IS 'Annualised business case: measured model uplift applied to published UK APP-fraud baselines. Assumptions in basis column.'")
display(spark.table(f"{CATALOG}.{ML}.business_case").orderBy("sort_order"))
print(f"ROI multiple: {(total_value) / PLATFORM_RUN_COST:.1f}x  | payback: {12 * PLATFORM_RUN_COST / total_value:.1f} months")
```
**Output:**

| sort_order | metric_key | metric | value | unit | basis | is_total |
|---|---|---|---|---|---|---|
| 1 | rules_value_recall | Scam value held by today's rules (hold-out test) | 0.5864 | pct | Measured: model_evaluation, same alert budget | False |
| 2 | model_value_recall | Scam value held by ML model (hold-out test) | 0.9559 | pct | Measured: model_evaluation, same alert budget | False |
| 3 | nb_losses_today | Northbridge APP scam losses today (per year) | 11718200.0 | GBP | UK Finance 2024 APP losses GBP 450.7m x 2.6% PCA share (assumption) | False |
| 4 | attempted_scam_value | Implied attempted scam value (per year) | 18079177.9807 | GBP | losses / (1 - rules recall x 60% intervention success) | False |
| 5 | customer_losses_prevented | Customer losses prevented (per year) | 4008153.7583 | GBP | attempted x (model recall - rules recall) x intervention success | False |
| 6 | annual_net_saving_gbp | Northbridge net reimbursement cost avoided | 1763587.6537 | GBP | prevented x 88% reimbursed (PSR) x 50% after receiving-PSP share | False |
| 7 | analyst_hours_saved | Analyst hours released (per year) | 29200.0 | hours | 1,200 holds/day x (11 -> 7 min) with GenAI case notes | False |
| 8 | analyst_value_gbp | Value of analyst capacity released | 1109600.0 | GBP | hours x GBP 38/h loaded cost (redeploy to complex cases) | False |
| 9 | genuine_holds_per_scam_rules | Genuine customers held per scam caught: rules | 13.881 | ratio | Measured: 1/precision - 1 | False |
| 10 | genuine_holds_per_scam_model | Genuine customers held per scam caught: model | 2.0845 | ratio | Measured: Consumer Duty friction indicator | False |
| 11 | platform_run_cost | Platform run cost (per year) | -180000.0 | GBP | Estimate: serverless pipeline + Lakebase + serving + FMAPI + app | False |
| 12 | total_annual_value | Net annual value to Northbridge | 2693187.6537 | GBP | net reimbursement avoided + analyst capacity - run cost | True |

```text
ROI multiple: 16.0x  | payback: 0.8 months
```
