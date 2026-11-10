# Follow one payment through the whole journey: `FP26001105668`

Captured 2026-11-10 09:18 UTC with real queries against the deployed build (`scripts/trace_one_payment.py`). This payment is the top-risk alert of the live window. **The legacy rules engine did not flag it, the model did**, Claude wrote the case note, an analyst stopped it in the app, and the decision flowed back into Unity Catalog.

`raw JSON in Volume → bronze → silver → (masked customer) → gold features → ML score → GenAI note → Lakebase → app decision → Lakehouse Sync → Genie`

## 0 · Raw file landed in the UC Volume (synthetic payments-hub feed)

File: `/Volumes/serverless_stable_my49a8_catalog/northbridge_raw/landing/payments/payments_2026-11-07.json`. The exact JSON line:

```json
{
  "payment_id": "FP26001105668",
  "event_ts": "2026-11-07T06:23:13Z",
  "payment_type": "FPS_SINGLE",
  "debtor": {
    "account_id": "A30040870",
    "customer_id": "C1040870"
  },
  "creditor": {
    "payee_id": "P2120649",
    "name": "Freya Wright",
    "sort_code": "74-26-12",
    "bank_name": "Brightpay EMI"
  },
  "amount": {
    "value": 8551.7,
    "currency": "GBP"
  },
  "reference": "thanks!",
  "payee_added_ts": "2026-10-13T15:28:00Z",
  "confirmation_of_payee": {
    "result": "MATCH"
  },
  "channel_context": {
    "channel": "MOBILE",
    "device_id": "dev-655021",
    "device_age_days": 455,
    "session_duration_sec": 102,
    "login_to_payment_sec": 203,
    "on_active_call": false
  }
}
```
## 1 · Lakeflow bronze (`northbridge_fraud.bronze_payments`, Auto Loader streaming table)

| field | value |
|---|---|
| _ingested_at | 2026-11-09T23:30:14.961Z |
| _source_file | /Volumes/serverless_stable_my49a8_catalog/northbridge_raw/landing/payments/payments_2026-11-07.json |
| amount | 8551.7 |
| customer_id | C1040870 |
| payment_id | FP26001105668 |
| reference | thanks! |
## 2 · Lakeflow silver (`silver_payments`: flattened, 7 expectations passed, de-duplicated by AUTO CDC)

| field | value |
|---|---|
| amount_gbp | 8551.7 |
| channel | MOBILE |
| cop_result | MATCH |
| customer_id | C1040870 |
| event_ts | 2026-11-07T06:23:13.000Z |
| on_active_call | false |
| payee_bank_name | Brightpay EMI |
| payee_id | P2120649 |
| payment_id | FP26001105668 |
| session_duration_sec | 102 |
## 3 · Unity Catalog governance on the customer (masked for every non-PII reader, incl. this query)

| field | value |
|---|---|
| age_band | 50-64 |
| customer_id | C1040870 |
| date_of_birth | 1973-01-01 |
| email | m*******************************k |
| evaluated_as | zeeshan.dar@databricks.com |
| full_name | M**************n |
| postcode | W*****M |
| postcode_district | WV1 |
| vulnerability_flag | false |
## 4 · Lakeflow gold (`gold_payment_features`): point-in-time features + what the LEGACY RULES decided

| field | value |
|---|---|
| amount_to_cust_avg_ratio | 2.745 |
| cop_result | MATCH |
| is_new_payee | false |
| legacy_rules_alert | false |
| minutes_since_payee_added | 35455.2 |
| on_active_call | false |
| payee_account_age_days | 41 |
| payee_bank_type | EMI |
| payee_distinct_senders_7d | 1 |
| payment_id | FP26001105668 |
| prior_payments_to_payee | 3 |
| reference_risk_keyword | false |
## 5 · ML (`payment_risk_scores`): UC model @champion score + reason codes

| field | value |
|---|---|
| model_alert | true |
| model_version | 5 |
| payment_id | FP26001105668 |
| reason_codes | ["Payee added only 25 days ago", "High payment value (GBP 8,552)", "Only 3 previous payment(s) to this payee"] |
| risk_band | CRITICAL |
| risk_score | 0.999106 |
| scored_at | 2026-11-10T09:10:13.369Z |
## 6 · GenAI (`northbridge_ml.alert_queue`): case note written by Claude via `ai_query`

| field | value |
|---|---|
| alert_id | AL-FP26001105668 |
| analyst_summary | The £8,551.70 mobile payment is 2.745 times this customer's 90-day average and goes to a payee added about 25 days ago, held at an EMI whose account is only 41 days old, with a vague reference of "thanks!" and just one sender in the last 7 days. Mitigating factors include a Confirmation of Payee match, three earlier payments to this payee, and no active call in progress, so the signals justify a conversation but do not yet confirm a scam. |
| customer_call_script | Can you talk me through what this payment of £8,551.70 is for?\|How did you come to set up this payee, and what do you know about them?\|What would you like us to know about how this payment came about today? |
| enriched_at | 2026-11-10T09:10:44.660Z |
| genai_confidence | medium |
| genai_model | databricks-claude-haiku-5-5 |
| recommended_action | HOLD_AND_CALL |
| suspected_scam_type | unclear |
## 7 · Lakebase (`northbridge_ops.alert_queue`): the synced Postgres row the app reads, plus sync status

| field | value |
|---|---|
| alert_id | AL-FP26001105668 |
| amount_gbp | 8551.7 |
| customer_display_name | M**************n |
| recommended_action | HOLD_AND_CALL |
| risk_band | CRITICAL |
| sla_due_ts | 2026-11-07T10:23:13.000Z |
| suspected_scam_type | unclear |

```json
{
  "detailed_state": "SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE",
  "last_sync": {
    "delta_table_sync_info": {
      "delta_commit_time": "2026-11-10T09:13:27Z",
      "delta_commit_version": 12
    },
    "sync_end_time": "2026-11-10T09:14:39.898443Z",
    "sync_start_time": "2026-11-10T09:14:37.455857Z"
  },
  "project": "projects/northbridge-scam-ops"
}
```
## 8 · App → Lakebase → UC: the analyst decision written by the Scam Shield app, streamed back by Lakehouse Sync

| _pg_change_type | alert_id | amount_protected_gbp | analyst | created_at | customer_contacted | decision | model_risk_score | notes | synced_to_uc_at |
|---|---|---|---|---|---|---|---|---|---|
| insert | AL-FP26001105668 | 8551.70 | zeeshan.dar@databricks.com | 2026-11-10T08:25:15.851Z | true | CONFIRMED_SCAM_STOPPED | 0.999106 | Customer confirmed caller claimed to be from Northbridge fraud team and asked to move money to a safe account. Payment stopped. | 2026-11-10T08:25:16.350 |

| _pg_change_type | alert_id | assigned_to | status | updated_at |
|---|---|---|---|---|
| insert | AL-FP26001105668 | zeeshan.dar@databricks.com | IN_REVIEW | 2026-11-10T08:25:08.033Z |
| update_preimage | AL-FP26001105668 | zeeshan.dar@databricks.com | IN_REVIEW | 2026-11-10T08:25:08.033Z |
| update_postimage | AL-FP26001105668 | zeeshan.dar@databricks.com | CLOSED | 2026-11-10T08:25:15.851Z |
## 9 · Genie Agent: the same payment, asked in plain English

**Q:** What happened to payment FP26001105668? …

**Genie:** Payment FP26001105668 was for **GBP 8,551.70** with model risk band **CRITICAL**. For payment FP26001105668, legacy rules alerted = **false**, the GenAI suggested scam type was **unclear**, and the analyst decision was **CONFIRMED_SCAM_STOPPED**.

```sql
WITH `latest_alert` AS (
  SELECT
    `payment_id`,
    `suspected_scam_type`,
    `alert_id`,
    ROW_NUMBER() OVER (
      PARTITION BY `payment_id`
      ORDER BY `enriched_at` DESC, `alert_id` DESC
    ) AS `rn`
  FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`alert_queue`
  WHERE `payment_id` = 'FP26001105668'
),
`latest_decision` AS (
  SELECT
    `alert_id`,
    `decision`,
    ROW_NUMBER() OVER (
      PARTITION BY `alert_id`
      ORDER BY `created_at` DESC, `decision_id` DESC
    ) AS `rn`
  FROM `serverless_stable_my49a8_catalog`.`northbridge_ops_history`.`lb_case_decisions_history`
  WHERE `_pg_change_type` = 'insert'
)
SELECT
  prs.`payment_id`,
  prs.`amount_gbp`,
  prs.`risk_band` AS `model_risk_band`,
  prs.`rules_alert` AS `legacy_rules_alerted`,
  la.`suspected_scam_type` AS `genai_suggested_scam_type`,
  ld.`decision` AS `analyst_decision`
FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`payment_risk_scores` AS prs
LEFT JOIN `latest_alert` AS la
  ON prs.`payment_id` = la.`payment_id`
 AND la.`rn` = 1
LEFT JOIN `latest_decision` AS ld
  ON la.`alert_id` = ld.`alert_id`
 AND ld.`rn` = 1
WHERE prs.`payment_id` = 'FP26001105668'
```
## 10 · Unity Catalog lineage for the tables this payment passed through

| source | target |
|---|---|
| alert_queue | alert_queue |
| gold_payment_features | alert_queue |
| payment_risk_scores | alert_queue |
| silver_customers | alert_queue |
| silver_payees | alert_queue |
| customer_profile | customer_profile |
| gold_payment_features | customer_profile |
| silver_customers | customer_profile |
| silver_accounts | gold_payment_features |
| silver_customers | gold_payment_features |
| silver_payees | gold_payment_features |
| silver_payments | gold_payment_features |
| silver_scam_claims | gold_payment_features |
| silver_payments_validated | silver_payments |
| bronze_payments | silver_payments_validated |
