# Lakeflow pipeline run log: `northbridge-app-fraud-medallion`

Pipeline id `f05e573a-38cd-421c-85d2-ccbd15b5cb2a` · serverless · Photon · catalog `serverless_stable_my49a8_catalog`, schema `northbridge_fraud` · exported 2026-11-10 08:50 UTC from the pipeline **event log** (`event_log('f05e573a-38cd-421c-85d2-ccbd15b5cb2a')`, queried on SQL warehouse `1035b8c40230fe40`) by `scripts/export_pipeline_log.py`.

## All pipeline updates

| cause | final_state | finished | full_refresh | started | update_id |
|---|---|---|---|---|---|
| JOB_TASK | COMPLETED | 2026-11-09T23:06:52.603Z | false | 2026-11-09T23:05:17.699Z | 95e8054d-cecd-4d4d-a2b8-70578d1f9710 |
| JOB_TASK | COMPLETED | 2026-11-09T23:14:45.025Z | false | 2026-11-09T23:14:05.097Z | eea7d666-965c-42c8-93b8-68af20ead3c4 |
| JOB_TASK | COMPLETED | 2026-11-09T23:31:12.296Z | true | 2026-11-09T23:29:38.512Z | 1019bcf1-afa0-46f3-9059-da563c893001 |
| JOB_TASK | COMPLETED | 2026-11-10T00:25:01.857Z | false | 2026-11-10T00:23:33.064Z | 958c7547-7fff-41b2-a49b-d8f9c36646c6 |

The second-to-last update is the **full refresh** (initial load of 89 days); the last is the **incremental** update triggered by the job for business day 2026-11-08.

## Update `1019bcf1-afa0-46f3-9059-da563c893001` · COMPLETED · full_refresh=true · 2026-11-09T23:29:38.512Z → 2026-11-09T23:31:12.296Z

### Flows (final status and rows written in this update)

| final_status | flow | rows_upserted_auto_cdc | rows_written |
|---|---|---|---|
| COMPLETED | bronze_accounts |  | 50000 |
| COMPLETED | bronze_customers |  | 50000 |
| COMPLETED | bronze_payees |  | 121100 |
| COMPLETED | bronze_payments |  | 1120109 |
| COMPLETED | bronze_scam_claims |  | 2750 |
| COMPLETED | gold_daily_fraud_kpis |  | 89 |
| COMPLETED | gold_mule_watchlist |  | 1322 |
| COMPLETED | gold_payment_features |  | 1114969 |
| COMPLETED | silver_accounts |  | 50000 |
| COMPLETED | silver_customers |  | 50000 |
| COMPLETED | silver_payees |  | 121100 |
| COMPLETED | silver_payments_dedupe | 1114969 |  |
| COMPLETED | silver_payments_quarantine |  | 2912 |
| COMPLETED | silver_payments_validated |  | 1117197 |
| COMPLETED | silver_scam_claims |  | 2750 |

### Data-quality expectations in this update

| dataset | expectation | failed | passed |
|---|---|---|---|
| silver_payments_validated | amount_positive | 2912 | 1117197 |
| silver_payments_validated | amount_present | 1818 | 1118291 |
| silver_payments_validated | event_ts_present | 0 | 1120109 |
| silver_payments_validated | fps_limit | 1818 | 1118291 |
| silver_payments_validated | gbp_only | 0 | 1120109 |
| silver_payments_validated | no_rescued_data | 0 | 1120109 |
| silver_payments_validated | payment_id_present | 0 | 1120109 |
| silver_scam_claims | claim_has_payment | 0 | 2750 |
| silver_scam_claims | valid_outcome | 0 | 2750 |

Rows dropped by `ON VIOLATION DROP ROW` expectations in this update: **2912**

### Event log (chronological)

| event_type | flow | level | message | timestamp |
|---|---|---|---|---|
| create_update |  | INFO | Update 1019bc started by JOB_TASK. | 2026-11-09T23:29:38.526Z |
| update_progress |  | INFO | Update 1019bc is WAITING_FOR_RESOURCES. | 2026-11-09T23:29:41.285Z |
| update_progress |  | INFO | Update 1019bc is INITIALIZING. | 2026-11-09T23:29:49.141Z |
| update_progress |  | INFO | Update 1019bc is RESETTING. | 2026-11-09T23:29:56.535Z |
| update_progress |  | INFO | Update 1019bc is SETTING_UP_TABLES. | 2026-11-09T23:29:57.949Z |
| update_progress |  | INFO | Update 1019bc is RUNNING. | 2026-11-09T23:30:04.957Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers' is STARTING. | 2026-11-09T23:30:05.165Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims' is STARTING. | 2026-11-09T23:30:10.686Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees' is STARTING. | 2026-11-09T23:30:11.356Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments' is STARTING. | 2026-11-09T23:30:12.013Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts' is STARTING. | 2026-11-09T23:30:12.650Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts' has COMPLETED. | 2026-11-09T23:30:19.737Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers' has COMPLETED. | 2026-11-09T23:30:19.752Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees' has COMPLETED. | 2026-11-09T23:30:19.757Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims' has COMPLETED. | 2026-11-09T23:30:19.894Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:30:22.319Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts' is STARTING. | 2026-11-09T23:30:22.335Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:30:22.368Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims' is STARTING. | 2026-11-09T23:30:22.383Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:30:22.451Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers' is STARTING. | 2026-11-09T23:30:22.454Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:30:22.498Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees' is STARTING. | 2026-11-09T23:30:22.500Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees' has COMPLETED. | 2026-11-09T23:30:26.159Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts' has COMPLETED. | 2026-11-09T23:30:26.246Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims' has COMPLETED. | 2026-11-09T23:30:27.084Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers' has COMPLETED. | 2026-11-09T23:30:27.215Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments' has COMPLETED. | 2026-11-09T23:30:29.443Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated' is STARTING. | 2026-11-09T23:30:29.604Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine' is STARTING. | 2026-11-09T23:30:30.275Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine' has COMPLETED. | 2026-11-09T23:30:33.187Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated' has COMPLETED. | 2026-11-09T23:30:36.923Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe' is STARTING. | 2026-11-09T23:30:37.240Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe' has COMPLETED. | 2026-11-09T23:30:52.202Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:30:53.324Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features' is STARTING. | 2026-11-09T23:30:53.327Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features' has COMPLETED. | 2026-11-09T23:31:09.338Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:31:09.553Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist' is STARTING. | 2026-11-09T23:31:09.555Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-09T23:31:09.727Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis' is STARTING. | 2026-11-09T23:31:09.730Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis' has COMPLETED. | 2026-11-09T23:31:12.039Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist' has COMPLETED. | 2026-11-09T23:31:12.267Z |
| update_progress |  | INFO | Update 1019bc is COMPLETED. | 2026-11-09T23:31:12.296Z |

## Update `958c7547-7fff-41b2-a49b-d8f9c36646c6` · COMPLETED · full_refresh=false · 2026-11-10T00:23:33.064Z → 2026-11-10T00:25:01.857Z

### Flows (final status and rows written in this update)

| final_status | flow | rows_upserted_auto_cdc | rows_written |
|---|---|---|---|
| COMPLETED | bronze_accounts |  |  |
| COMPLETED | bronze_customers |  |  |
| COMPLETED | bronze_payees |  |  |
| COMPLETED | bronze_payments |  | 12676 |
| COMPLETED | bronze_scam_claims |  | 42 |
| COMPLETED | gold_daily_fraud_kpis |  | 90 |
| COMPLETED | gold_mule_watchlist |  | 1336 |
| COMPLETED | gold_payment_features |  | 1127588 |
| COMPLETED | silver_accounts |  | 50000 |
| COMPLETED | silver_customers |  | 50000 |
| COMPLETED | silver_payees |  | 121100 |
| COMPLETED | silver_payments_dedupe | 12619 |  |
| COMPLETED | silver_payments_quarantine |  | 34 |
| COMPLETED | silver_payments_validated |  | 12642 |
| COMPLETED | silver_scam_claims |  | 2792 |

### Data-quality expectations in this update

| dataset | expectation | failed | passed |
|---|---|---|---|
| silver_payments_validated | amount_positive | 34 | 12642 |
| silver_payments_validated | amount_present | 19 | 12657 |
| silver_payments_validated | event_ts_present | 0 | 12676 |
| silver_payments_validated | fps_limit | 19 | 12657 |
| silver_payments_validated | gbp_only | 0 | 12676 |
| silver_payments_validated | no_rescued_data | 0 | 12676 |
| silver_payments_validated | payment_id_present | 0 | 12676 |
| silver_scam_claims | claim_has_payment | 0 | 2792 |
| silver_scam_claims | valid_outcome | 0 | 2792 |

Rows dropped by `ON VIOLATION DROP ROW` expectations in this update: **34**

### Event log (chronological)

| event_type | flow | level | message | timestamp |
|---|---|---|---|---|
| create_update |  | INFO | Update 958c75 started by JOB_TASK. | 2026-11-10T00:23:33.079Z |
| update_progress |  | INFO | Update 958c75 is WAITING_FOR_RESOURCES. | 2026-11-10T00:23:36.514Z |
| update_progress |  | INFO | Update 958c75 is INITIALIZING. | 2026-11-10T00:23:44.751Z |
| update_progress |  | INFO | Update 958c75 is SETTING_UP_TABLES. | 2026-11-10T00:23:55.972Z |
| update_progress |  | INFO | Update 958c75 is RUNNING. | 2026-11-10T00:23:59.100Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers' is STARTING. | 2026-11-10T00:23:59.316Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims' is STARTING. | 2026-11-10T00:24:04.814Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees' is STARTING. | 2026-11-10T00:24:05.308Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments' is STARTING. | 2026-11-10T00:24:05.836Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts' is STARTING. | 2026-11-10T00:24:06.336Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_customers' has COMPLETED. | 2026-11-10T00:24:08.745Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payees' has COMPLETED. | 2026-11-10T00:24:08.770Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_accounts' has COMPLETED. | 2026-11-10T00:24:09.014Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts' has been planned to be executed as NO_OP. | 2026-11-10T00:24:13.955Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees' has been planned to be executed as NO_OP. | 2026-11-10T00:24:13.975Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers' has been planned to be executed as NO_OP. | 2026-11-10T00:24:13.978Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts' is STARTING. | 2026-11-10T00:24:13.982Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees' is STARTING. | 2026-11-10T00:24:13.993Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers' is STARTING. | 2026-11-10T00:24:13.999Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_scam_claims' has COMPLETED. | 2026-11-10T00:24:14.826Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.bronze_payments' has COMPLETED. | 2026-11-10T00:24:15.005Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine' is STARTING. | 2026-11-10T00:24:16.198Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payees' has COMPLETED. | 2026-11-10T00:24:16.208Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_accounts' has COMPLETED. | 2026-11-10T00:24:16.309Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_customers' has COMPLETED. | 2026-11-10T00:24:16.353Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated' is STARTING. | 2026-11-10T00:24:16.716Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_quarantine' has COMPLETED. | 2026-11-10T00:24:21.724Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_validated' has COMPLETED. | 2026-11-10T00:24:21.731Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims' has been planned to be executed as WINDOW_FUNCTION. | 2026-11-10T00:24:22.260Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims' is STARTING. | 2026-11-10T00:24:22.273Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe' is STARTING. | 2026-11-10T00:24:24.573Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_scam_claims' has COMPLETED. | 2026-11-10T00:24:28.469Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.silver_payments_dedupe' has COMPLETED. | 2026-11-10T00:24:32.958Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features' has been planned to be executed as COMPLETE_RECOMPUTE. | 2026-11-10T00:24:37.390Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features' is STARTING. | 2026-11-10T00:24:37.400Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features' has COMPLETED. | 2026-11-10T00:24:53.106Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist' has been planned to be executed as GENERIC_AGGREGATE. | 2026-11-10T00:24:55.834Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist' is STARTING. | 2026-11-10T00:24:55.841Z |
| planning_information | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis' has been planned to be executed as GROUP_AGGREGATE. | 2026-11-10T00:24:56.047Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis' is STARTING. | 2026-11-10T00:24:56.051Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_mule_watchlist' has COMPLETED. | 2026-11-10T00:25:00.697Z |
| flow_progress | serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis | INFO | Flow 'serverless_stable_my49a8_catalog.northbridge_fraud.gold_daily_fraud_kpis' has COMPLETED. | 2026-11-10T00:25:01.825Z |
| update_progress |  | INFO | Update 958c75 is COMPLETED. | 2026-11-10T00:25:01.857Z |
