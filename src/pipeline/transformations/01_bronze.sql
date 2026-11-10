-- =====================================================================================
-- BRONZE  ·  Lakeflow Spark Declarative Pipeline  ·  Auto Loader incremental ingestion
-- Raw files land in the UC Volume /Volumes/<catalog>/northbridge_raw/landing/...
-- Every bronze row keeps lineage columns (_source_file, _ingested_at) for audit.
-- =====================================================================================

CREATE OR REFRESH STREAMING TABLE bronze_payments
COMMENT "Faster Payments hub events (nested JSON, 1 file per business day) ingested incrementally with Auto Loader. Raw, unvalidated, may contain duplicates."
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'payments_hub')
AS SELECT
  *,
  _metadata.file_path              AS _source_file,
  _metadata.file_modification_time AS _file_modified_at,
  current_timestamp()              AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/payments/',
  format => 'json',
  schema => 'payment_id STRING, event_ts TIMESTAMP, payment_type STRING,
             debtor STRUCT<account_id: STRING, customer_id: STRING>,
             creditor STRUCT<payee_id: STRING, name: STRING, sort_code: STRING, bank_name: STRING>,
             amount STRUCT<value: DOUBLE, currency: STRING>,
             reference STRING, payee_added_ts TIMESTAMP,
             confirmation_of_payee STRUCT<result: STRING>,
             channel_context STRUCT<channel: STRING, device_id: STRING, device_age_days: INT,
                                    session_duration_sec: INT, login_to_payment_sec: INT, on_active_call: BOOLEAN>',
  rescuedDataColumn => '_rescued_data'
);

CREATE OR REFRESH STREAMING TABLE bronze_customers
COMMENT "Core banking customer extract (CSV). Contains direct PII - restricted to data engineering; consumers use silver_customers (masked)."
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'core_banking', 'contains_pii' = 'true')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/customers/', format => 'csv', header => true,
  schema => 'customer_id STRING, full_name STRING, date_of_birth DATE, email STRING, mobile_phone STRING, postcode STRING,
             region STRING, segment STRING, vulnerability_flag BOOLEAN, tenure_months INT, digital_active BOOLEAN, extract_ts TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE bronze_accounts
COMMENT "Core banking current-account extract (CSV)."
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'core_banking', 'contains_pii' = 'true')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/accounts/', format => 'csv', header => true,
  schema => 'account_id STRING, customer_id STRING, sort_code STRING, account_number STRING, product STRING,
             opened_date DATE, current_balance_gbp DOUBLE, extract_ts TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE bronze_payees
COMMENT "Beneficiary register + inter-bank data-sharing intelligence (receiving account opened date where shared)."
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'payee_intelligence')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/payees/', format => 'csv', header => true,
  schema => 'payee_id STRING, payee_name STRING, payee_category STRING, payee_bank_name STRING, payee_bank_type STRING,
             payee_sort_code STRING, payee_account_opened_date DATE, intel_source STRING, extract_ts TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE bronze_scam_claims
COMMENT "APP scam claims from the complaints & reimbursement system (PSR reimbursement requirement). Source of ground-truth labels, arrives with a lag."
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'complaints_reimbursement')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/scam_claims/', format => 'csv', header => true,
  schema => 'claim_id STRING, customer_id STRING, payment_id STRING, reported_ts TIMESTAMP, scam_type_reported STRING,
             claimed_amount_gbp DOUBLE, outcome STRING, rejection_reason STRING, reimbursed_amount_gbp DOUBLE,
             receiving_psp_contribution_gbp DOUBLE');
