# Platform evidence: live query results

Captured 2026-11-10 09:16 UTC against workspace `fevm-serverless-stable-my49a8` via `databricks experimental aitools tools query` (SQL warehouse `1035b8c40230fe40`).
Pipeline id: `f05e573a-38cd-421c-85d2-ccbd15b5cb2a`. Every block below is the real query and its real result.

## 1. Lakeflow: rows per medallion table

```sql
SELECT 'bronze_payments' AS table_name, count(*) AS rows FROM serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments UNION ALL
SELECT 'silver_payments_validated', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated UNION ALL
SELECT 'silver_payments_quarantine', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine UNION ALL
SELECT 'silver_payments (AUTO CDC de-duplicated)', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments UNION ALL
SELECT 'silver_customers', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers UNION ALL
SELECT 'silver_payees', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees UNION ALL
SELECT 'silver_scam_claims', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims UNION ALL
SELECT 'gold_payment_features', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features UNION ALL
SELECT 'gold_daily_fraud_kpis', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis UNION ALL
SELECT 'gold_mule_watchlist', count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist
```

| rows | table_name |
|---|---|
| 1127588 | silver_payments (AUTO CDC de-duplicated) |
| 2792 | silver_scam_claims |
| 1132785 | bronze_payments |
| 1129839 | silver_payments_validated |
| 2946 | silver_payments_quarantine |
| 50000 | silver_customers |
| 121100 | silver_payees |
| 1127588 | gold_payment_features |
| 90 | gold_daily_fraud_kpis |
| 1336 | gold_mule_watchlist |

## 2. Lakeflow: Auto Loader files ingested per source

```sql
SELECT regexp_extract(_source_file, 'landing/([a-z_]+)/', 1) AS source, count(DISTINCT _source_file) AS files, count(*) AS rows
FROM serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments GROUP BY 1 UNION ALL
SELECT 'scam_claims', count(DISTINCT _source_file), count(*) FROM serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims
```

| files | rows | source |
|---|---|---|
| 90 | 1132785 | payments |
| 89 | 2792 | scam_claims |

## 3. Lakeflow: data-quality expectations (pipeline event log, latest update)

```sql
WITH e AS (
  SELECT origin.flow_name AS flow, explode(from_json(details:flow_progress.data_quality.expectations,
         'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS x, timestamp
  FROM event_log('f05e573a-38cd-421c-85d2-ccbd15b5cb2a') WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL)
SELECT x.dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed
FROM e GROUP BY 1, 2 ORDER BY 1, 2
```

| dataset | expectation | failed | passed |
|---|---|---|---|
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | amount_positive | 5832 | 2244198 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | amount_present | 3614 | 2246416 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | event_ts_present | 0 | 2250030 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | fps_limit | 3614 | 2246416 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | gbp_only | 0 | 2250030 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | no_rescued_data | 0 | 2250030 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | payment_id_present | 0 | 2250030 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | claim_has_payment | 0 | 13766 |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | valid_outcome | 0 | 13766 |

## 4. Lakeflow: quarantine reasons

```sql
SELECT quarantine_reason, count(*) AS rows FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine GROUP BY 1 ORDER BY 2 DESC
```

| quarantine_reason | rows |
|---|---|
| missing_amount | 1837 |
| non_positive_amount | 1109 |

## 5. Lakeflow: pipeline updates (event log)

```sql
SELECT timestamp, details:update_progress.state AS state, origin.update_id
FROM event_log('f05e573a-38cd-421c-85d2-ccbd15b5cb2a') WHERE event_type = 'update_progress' AND details:update_progress.state IN ('COMPLETED', 'FAILED') ORDER BY timestamp DESC LIMIT 10
```

| state | timestamp | update_id |
|---|---|---|
| COMPLETED | 2026-11-10T09:04:27.478Z | f4b83762-3216-4414-8c4b-2478218fa083 |
| COMPLETED | 2026-11-10T00:25:01.857Z | 958c7547-7fff-41b2-a49b-d8f9c36646c6 |
| COMPLETED | 2026-11-09T23:31:12.296Z | 1019bcf1-afa0-46f3-9059-da563c893001 |
| COMPLETED | 2026-11-09T23:14:45.025Z | eea7d666-965c-42c8-93b8-68af20ead3c4 |
| COMPLETED | 2026-11-09T23:06:52.603Z | 95e8054d-cecd-4d4d-a2b8-70578d1f9710 |

## 6. Unity Catalog: column masks bound to tables

```sql
SELECT table_name, column_name, mask_name FROM serverless_stable_my49a8_catalog.information_schema.column_masks WHERE table_schema = 'northbridge_fraud' ORDER BY 1, 2
```

| column_name | mask_name | table_name |
|---|---|---|
| account_number | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_string | silver_accounts |
| sort_code | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_string | silver_accounts |
| date_of_birth | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_date | silver_customers |
| email | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_string | silver_customers |
| full_name | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_string | silver_customers |
| mobile_phone | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_string | silver_customers |
| postcode | serverless_stable_my49a8_catalog.northbridge_fraud.mask_pii_string | silver_customers |

## 7. Unity Catalog: what a non-PII reader sees (masked)

```sql
SELECT current_user() AS evaluated_as, customer_id, full_name, date_of_birth, email, postcode, postcode_district, age_band FROM serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers ORDER BY customer_id LIMIT 5
```

| age_band | customer_id | date_of_birth | email | evaluated_as | full_name | postcode | postcode_district |
|---|---|---|---|---|---|---|---|
| 35-49 | C1000000 | 1989-01-01 | s***************************k | zeeshan.dar@databricks.com | S**********s | N*****O | NW3 |
| 50-64 | C1000001 | 1962-01-01 | j**************************k | zeeshan.dar@databricks.com | J*********r | P*****W | PL1 |
| 75+ | C1000002 | 1937-01-01 | m****************************k | zeeshan.dar@databricks.com | M***********s | L*****Q | LN1 |
| 35-49 | C1000003 | 1985-01-01 | a***************************k | zeeshan.dar@databricks.com | A**********n | B*****T | B15 |
| 65-74 | C1000004 | 1960-01-01 | h****************************k | zeeshan.dar@databricks.com | H***********s | Y*****Y | YO1 |

## 8. Unity Catalog: governed tags

```sql
SELECT 'table' AS level, table_name AS object, tag_name, tag_value FROM serverless_stable_my49a8_catalog.information_schema.table_tags WHERE schema_name = 'northbridge_fraud' UNION ALL
SELECT 'column', concat(table_name, '.', column_name), tag_name, tag_value FROM serverless_stable_my49a8_catalog.information_schema.column_tags WHERE schema_name = 'northbridge_fraud'
ORDER BY 1 DESC, 2, 3
```

| level | object | tag_name | tag_value |
|---|---|---|---|
| table | bronze_accounts | data_classification | pii |
| table | bronze_accounts | nb_access_tier | restricted |
| table | bronze_accounts | nb_regulation | UK_GDPR |
| table | bronze_customers | data_classification | pii |
| table | bronze_customers | nb_access_tier | restricted |
| table | bronze_customers | nb_regulation | UK_GDPR |
| table | bronze_payees | nb_access_tier | confidential |
| table | bronze_payments | nb_access_tier | confidential |
| table | bronze_payments | nb_regulation | PSR_APP_REIMBURSEMENT |
| table | bronze_scam_claims | nb_access_tier | confidential |
| table | bronze_scam_claims | nb_regulation | PSR_APP_REIMBURSEMENT |
| table | gold_daily_fraud_kpis | nb_access_tier | internal |
| table | gold_daily_fraud_kpis | system.certification_status | certified |
| table | gold_mule_watchlist | nb_access_tier | confidential |
| table | gold_mule_watchlist | nb_sharing | interbank_data_sharing |
| table | gold_payment_features | nb_access_tier | internal |
| table | gold_payment_features | nb_ml_use | training_and_scoring |
| table | gold_payment_features | nb_pii_protection | no_direct_identifiers |
| table | silver_accounts | data_classification | pii |
| table | silver_accounts | nb_access_tier | confidential |
| table | silver_accounts | nb_pii_protection | column_masked |
| table | silver_customers | data_classification | pii |
| table | silver_customers | nb_access_tier | confidential |
| table | silver_customers | nb_pii_protection | column_masked |
| table | silver_customers | nb_regulation | UK_GDPR |
| table | silver_payments | nb_access_tier | confidential |
| table | silver_payments | nb_regulation | PSR_APP_REIMBURSEMENT |
| table | silver_scam_claims | nb_access_tier | confidential |
| table | silver_scam_claims | nb_regulation | PSR_APP_REIMBURSEMENT |
| column | bronze_accounts.account_number | class.bank_number |  |

_… 13 more rows_

## 9. Unity Catalog: lineage captured (system.access.table_lineage)

```sql
SELECT DISTINCT source_table_full_name, target_table_full_name FROM system.access.table_lineage
WHERE target_table_catalog = 'serverless_stable_my49a8_catalog' AND target_table_schema LIKE 'northbridge%' AND source_table_full_name IS NOT NULL
ORDER BY 2, 1
```

| source_table_full_name | target_table_full_name |
|---|---|
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features |
| serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts |
| serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers |
| serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments |
| serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine |
| serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated |
| serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_ml.alert_queue |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | serverless_stable_my49a8_catalog.northbridge_ml.alert_queue |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | serverless_stable_my49a8_catalog.northbridge_ml.alert_queue |
| serverless_stable_my49a8_catalog.northbridge_ml.payment_risk_scores | serverless_stable_my49a8_catalog.northbridge_ml.alert_queue |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_ml.app_scam_metrics |
| serverless_stable_my49a8_catalog.northbridge_ml.payment_risk_scores | serverless_stable_my49a8_catalog.northbridge_ml.app_scam_metrics |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_ml.customer_payee_history |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_ml.customer_profile |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | serverless_stable_my49a8_catalog.northbridge_ml.customer_profile |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | serverless_stable_my49a8_catalog.northbridge_ml.payee_profile |
| serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | serverless_stable_my49a8_catalog.northbridge_ml.payee_profile |
| serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | serverless_stable_my49a8_catalog.northbridge_ml.payee_profile |
| system.__internal_logging.payload_logs | serverless_stable_my49a8_catalog.northbridge_ml.scam_risk_serving_payload |
| serverless_stable_my49a8_catalog.northbridge_ml.alert_queue | serverless_stable_my49a8_catalog.northbridge_ops.alert_queue |
| serverless_stable_my49a8_catalog.northbridge_ml.customer_payee_history | serverless_stable_my49a8_catalog.northbridge_ops.customer_payee_history |
| serverless_stable_my49a8_catalog.northbridge_ml.customer_profile | serverless_stable_my49a8_catalog.northbridge_ops.customer_profile |

_… 1 more rows_

## 10. Unity Catalog: schema grants

```sql
SELECT grantee, schema_name, privilege_type FROM serverless_stable_my49a8_catalog.information_schema.schema_privileges WHERE schema_name LIKE 'northbridge%' ORDER BY 2, 1, 3
```

| grantee | privilege_type | schema_name |
|---|---|---|
| account users | SELECT | northbridge_fraud |
| account users | USE_SCHEMA | northbridge_fraud |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | northbridge_fraud |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | northbridge_fraud |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | SELECT | northbridge_fraud |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | USE_SCHEMA | northbridge_fraud |
| zeeshan.dar@databricks.com | ALL_PRIVILEGES | northbridge_fraud |
| zeeshan.dar@databricks.com | MANAGE | northbridge_fraud |
| account users | EXECUTE | northbridge_ml |
| account users | SELECT | northbridge_ml |
| account users | USE_SCHEMA | northbridge_ml |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | northbridge_ml |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | northbridge_ml |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | EXECUTE | northbridge_ml |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | SELECT | northbridge_ml |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | USE_SCHEMA | northbridge_ml |
| zeeshan.dar@databricks.com | ALL_PRIVILEGES | northbridge_ml |
| zeeshan.dar@databricks.com | MANAGE | northbridge_ml |
| account users | SELECT | northbridge_ops |
| account users | USE_SCHEMA | northbridge_ops |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | northbridge_ops |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | northbridge_ops |
| zeeshan.dar@databricks.com | ALL_PRIVILEGES | northbridge_ops |
| zeeshan.dar@databricks.com | MANAGE | northbridge_ops |
| account users | SELECT | northbridge_ops_history |
| account users | USE_SCHEMA | northbridge_ops_history |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | northbridge_ops_history |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | northbridge_ops_history |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | SELECT | northbridge_ops_history |
| fabee2fc-7b58-4ba9-9885-75ea672ff64c | USE_SCHEMA | northbridge_ops_history |

_… 6 more rows_

## 11. ML: hold-out evaluation, rules vs model at the same alert budget

```sql
SELECT * FROM serverless_stable_my49a8_catalog.northbridge_ml.model_evaluation
```

| alerts | approach | count_recall | model_version | pr_auc | precision | roc_auc | scam_value_caught_gbp | scams_caught | test_window | value_recall |
|---|---|---|---|---|---|---|---|---|---|---|
| 1533 | rules_engine | 0.1686 | 5 |  | 0.0678 |  | 1387811.27 | 104 | 2026-10-10..2026-10-29 | 0.5827 |
| 1533 | ml_model_same_budget | 0.7812 | 5 | 0.609418707135091 | 0.3144 | 0.9957889147668766 | 2250955.03 | 482 | 2026-10-10..2026-10-29 | 0.945 |

## 12. ML: value recall by scam typology

```sql
SELECT * FROM serverless_stable_my49a8_catalog.northbridge_ml.model_recall_by_scam_type ORDER BY scam_value_gbp DESC
```

| model_value_recall | rules_value_recall | scam_payments | scam_type | scam_value_gbp |
|---|---|---|---|---|
| 0.982 | 0.689 | 117.0 | investment | 1440083.0 |
| 0.99 | 0.105 | 106.0 | romance | 364199.0 |
| 0.904 | 0.834 | 74.0 | impersonation | 327568.0 |
| 0.707 | 0.086 | 240.0 | purchase | 136381.0 |
| 0.748 | 0.779 | 24.0 | invoice_redirection | 94032.0 |
| 0.693 | 0.0 | 56.0 | advance_fee | 19596.0 |

## 13. ML: risk-band distribution over all scored payments

```sql
SELECT risk_band, count(*) AS payments, sum(is_app_scam) AS confirmed_scams, round(sum(CASE WHEN is_app_scam = 1 THEN amount_gbp END), 0) AS scam_value_gbp,
       sum(CASE WHEN rules_alert THEN 1 ELSE 0 END) AS rules_alerts, max(model_version) AS model_version
FROM serverless_stable_my49a8_catalog.northbridge_ml.payment_risk_scores GROUP BY 1 ORDER BY min(risk_score) DESC
```

| confirmed_scams | model_version | payments | risk_band | rules_alerts | scam_value_gbp |
|---|---|---|---|---|---|
| 783 | 5 | 860 | CRITICAL | 284 | 6081848.0 |
| 1686 | 5 | 7774 | HIGH | 995 | 3698297.0 |
| 70 | 5 | 5604 | MEDIUM | 546 | 61201.0 |
| 152 | 5 | 1113350 | LOW | 5112 | 158656.0 |

## 14. GenAI: alert queue enrichment summary (ai_query, Claude)

```sql
SELECT suspected_scam_type, recommended_action, count(*) AS alerts, round(avg(risk_score), 3) AS avg_risk,
       sum(CASE WHEN legacy_rules_would_alert THEN 0 ELSE 1 END) AS missed_by_rules, max(genai_model) AS model
FROM serverless_stable_my49a8_catalog.northbridge_ml.alert_queue GROUP BY 1, 2 ORDER BY 3 DESC
```

| alerts | avg_risk | missed_by_rules | model | recommended_action | suspected_scam_type |
|---|---|---|---|---|---|
| 91 | 0.926 | 72 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | purchase |
| 79 | 0.942 | 59 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | unclear |
| 45 | 0.932 | 37 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | advance_fee |
| 40 | 0.936 | 24 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | impersonation |
| 37 | 0.937 | 27 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | investment |
| 5 | 0.967 | 4 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | invoice_redirection |
| 2 | 0.996 | 1 | databricks-claude-haiku-5-5 |  |  |
| 1 | 0.976 | 1 | databricks-claude-haiku-5-5 | HOLD_AND_CALL | romance |

## 15. GenAI: three verbatim case notes

```sql
SELECT alert_id, round(amount_gbp, 2) AS amount_gbp, reference, reason_codes, suspected_scam_type, analyst_summary, customer_call_script, recommended_action
FROM serverless_stable_my49a8_catalog.northbridge_ml.alert_queue ORDER BY risk_score DESC LIMIT 3
```

| alert_id | amount_gbp | analyst_summary | customer_call_script | reason_codes | recommended_action | reference | suspected_scam_type |
|---|---|---|---|---|---|---|---|
| AL-FP26001105668 | 8551.7 | The £8,551.70 mobile payment is 2.745 times this customer's 90-day average and goes to a payee added about 25 days ago, held at an EMI whose account is only 41 days old, with a vague reference of "tha | Can you talk me through what this payment of £8,551.70 is for?\|How did you come to set up this payee, and what do you know about them?\|What would you like us to know about how this payment came abou | ["Payee added only 25 days ago", "High payment value (GBP 8,552)", "Only 3 previous payment(s) to this payee"] | HOLD_AND_CALL | thanks! | unclear |
| AL-FP26001124967 | 10384.21 | A GBP 10,384.21 mobile payment with the reference "flight" is 2.582 times this customer's 90-day average and goes to a payee added 26 days ago whose receiving account is only 42 days old at an EMI, wi | Can you tell me in your own words what this payment is for and what you expect to receive in return? \| How did you come to be paying this payee, and how did you first find out about them? \| What ste | ["Payee added only 26 days ago", "High payment value (GBP 10,384)", "Only 4 previous payment(s) to this payee"] | HOLD_AND_CALL | flight | purchase |
| AL-FP26001110725 | 200.38 | The receiving account is an EMI opened only 24 days ago, the payee was added about 46 hours before this payment, and Confirmation of Payee returned NO_MATCH, which together point to a payee that may n | Can you talk me through what this payment is for and how you came to choose this payee?\|What did you see or receive from the seller or payee, and how did you confirm their identity?\|When the account | ["Payee added only 46 hours ago", "Only 1 previous payment(s) to this payee", "Receiving account opened only 24 days ago"] | HOLD_AND_CALL | sofa | purchase |

## 16. Semantic layer: metric view query (MEASURE)

```sql
SELECT `Scam Type`, MEASURE(`Confirmed Scam Value GBP`) AS scam_value_gbp, MEASURE(`Rules Value Recall`) AS rules_value_recall,
       MEASURE(`Model Value Recall`) AS model_value_recall, MEASURE(`Net Reimbursement Cost GBP`) AS net_cost_gbp
FROM serverless_stable_my49a8_catalog.northbridge_ml.app_scam_metrics WHERE `Payment Date` BETWEEN '2026-10-10' AND '2026-10-29' AND `Scam Type` <> 'not a scam' GROUP BY ALL ORDER BY 2 DESC
```

| Scam Type | model_value_recall | net_cost_gbp | rules_value_recall | scam_value_gbp |
|---|---|---|---|---|
| investment | 0.9816960286410135 | 706169.6599999998 | 0.6886620036811624 | 1440083.1100000006 |
| romance | 0.9901898515038657 | 175327.24999999997 | 0.10461846475411354 | 364199.38 |
| impersonation | 0.9042508743988653 | 159843.56999999998 | 0.833595874321019 | 327567.89999999985 |
| purchase | 0.707411811184588 | 67349.94999999997 | 0.08575820252110924 | 136381.23999999996 |
| invoice_redirection | 0.7481701737118635 | 45248.62 | 0.7787093031479125 | 94032.15000000001 |
| advance_fee | 0.6925595112036248 | 9728.460000000001 | 0.0 | 19595.89 |

## 17. Business case table

```sql
SELECT sort_order, metric, round(value, 4) AS value, unit, basis FROM serverless_stable_my49a8_catalog.northbridge_ml.business_case ORDER BY sort_order
```

| basis | metric | sort_order | unit | value |
|---|---|---|---|---|
| Measured: model_evaluation, same alert budget | Scam value held by today's rules (hold-out test) | 1 | pct | 0.5827 |
| Measured: model_evaluation, same alert budget | Scam value held by ML model (hold-out test) | 2 | pct | 0.945 |
| UK Finance 2024 APP losses GBP 450.7m x 2.6% PCA share (assumption) | Northbridge APP scam losses today (per year) | 3 | GBP | 1.17182E7 |
| losses / (1 - rules recall x 60% intervention success) | Implied attempted scam value (per year) | 4 | GBP | 1.80174667118E7 |
| attempted x (model recall - rules recall) x intervention success | Customer losses prevented (per year) | 5 | GBP | 3916636.9138 |
| prevented x 88% reimbursed (PSR) x 50% after receiving-PSP share | Northbridge net reimbursement cost avoided | 6 | GBP | 1723320.2421 |
| 1,200 holds/day x (11 -> 7 min) with GenAI case notes | Analyst hours released (per year) | 7 | hours | 29200.0 |
| hours x GBP 38/h loaded cost (redeploy to complex cases) | Value of analyst capacity released | 8 | GBP | 1109600.0 |
| Measured: 1/precision - 1 | Genuine customers held per scam caught: rules | 9 | ratio | 13.7493 |
| Measured: Consumer Duty friction indicator | Genuine customers held per scam caught: model | 10 | ratio | 2.1807 |
| Estimate: serverless pipeline + Lakebase + serving + FMAPI + app | Platform run cost (per year) | 11 | GBP | -180000.0 |
| net reimbursement avoided + analyst capacity - run cost | Net annual value to Northbridge | 12 | GBP | 2652920.2421 |

## 18. Lakebase synced tables registered in UC

```sql
SELECT table_name, table_type, comment FROM serverless_stable_my49a8_catalog.information_schema.tables WHERE table_schema = 'northbridge_ops' ORDER BY 1
```

| comment | table_name | table_type |
|---|---|---|
|  | __585a1b0c_2cbb_4650_817b_ce7fba453f4e_databricks_postgres_northbridge_ops_alert_queue_6292bae3_a7fe_40c5_905f_191e748ffdb5 | MANAGED |
|  | alert_queue | FOREIGN |
| Database table synced from another UC table | customer_payee_history | FOREIGN |
| Database table synced from another UC table | customer_profile | FOREIGN |
|  | event_log_2239cd0c_9ec3_44e7_954c_e4adae927f00 | MANAGED |
|  | event_log_585a1b0c_2cbb_4650_817b_ce7fba453f4e | MANAGED |
|  | event_log_5b15440a_ed37_4ffe_a6f0_4e47396891a2 | MANAGED |
|  | event_log_93d3a9fc_a9e5_43ab_acf8_657a91fe6792 | MANAGED |
| Database table synced from another UC table | payee_profile | FOREIGN |

## 19. Lakehouse Sync: analyst decisions flowing back from Lakebase to UC

```sql
SELECT _pg_change_type, decision, count(*) AS rows, round(sum(amount_protected_gbp), 2) AS amount_protected_gbp, max(_timestamp) AS last_change
FROM serverless_stable_my49a8_catalog.northbridge_ops_history.lb_case_decisions_history GROUP BY 1, 2 ORDER BY 1, 2
```

| _pg_change_type | amount_protected_gbp | decision | last_change | rows |
|---|---|---|---|---|
| insert | 28421.71 | CONFIRMED_SCAM_STOPPED | 2026-11-10T08:34:26.676 | 3 |
| insert | 80146.41 | REFERRED_TO_POLICE | 2026-11-10T08:34:28.395 | 9 |

## 20. Lakehouse Sync: live payment checks logged by the app

```sql
SELECT risk_band, action, count(*) AS checks, round(avg(lookup_ms), 1) AS avg_lakebase_lookup_ms, round(avg(scoring_ms), 1) AS avg_model_serving_ms
FROM serverless_stable_my49a8_catalog.northbridge_ops_history.lb_payment_checks_history WHERE _pg_change_type = 'insert' GROUP BY 1, 2 ORDER BY 1
```

| action | avg_lakebase_lookup_ms | avg_model_serving_ms | checks | risk_band |
|---|---|---|---|---|
| HOLD_AND_CALL | 10.7 | 12979.2 | 3 | HIGH |
| RELEASE | 9.8 | 2028.0 | 6 | LOW |

## 21. Model Serving: inference table (AI Gateway) request log

```sql
SELECT date(request_time) AS day, count(*) AS requests, round(avg(execution_duration_ms), 1) AS avg_exec_ms, max(served_entity_id) IS NOT NULL AS logged
FROM serverless_stable_my49a8_catalog.northbridge_ml.scam_risk_serving_payload GROUP BY 1 ORDER BY 1 DESC LIMIT 5
```

| avg_exec_ms | day | logged | requests |
|---|---|---|---|
| 21.4 | 2026-11-10 | true | 19 |
| 25.6 | 2026-11-09 | true | 10 |
