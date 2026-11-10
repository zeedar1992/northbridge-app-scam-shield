-- =====================================================================================
-- SILVER  ·  validated, typed, de-duplicated, PII column-masked (Unity Catalog masks)
-- =====================================================================================

-- 1) Flatten + validate. Expectations drop bad rows and are tracked in the pipeline event log.
CREATE OR REFRESH STREAMING TABLE silver_payments_validated (
  CONSTRAINT payment_id_present EXPECT (payment_id IS NOT NULL)                     ON VIOLATION DROP ROW,
  CONSTRAINT amount_present     EXPECT (amount_gbp IS NOT NULL)                     ON VIOLATION DROP ROW,
  CONSTRAINT amount_positive    EXPECT (amount_gbp > 0)                             ON VIOLATION DROP ROW,
  CONSTRAINT event_ts_present   EXPECT (event_ts IS NOT NULL)                       ON VIOLATION DROP ROW,
  CONSTRAINT gbp_only           EXPECT (currency = 'GBP'),
  CONSTRAINT fps_limit          EXPECT (amount_gbp <= 1000000)                      ON VIOLATION DROP ROW,
  CONSTRAINT no_rescued_data    EXPECT (_rescued_data IS NULL)
)
COMMENT "Flattened Faster Payments with data-quality expectations applied (null/negative amounts dropped). Still may contain at-least-once duplicates."
TBLPROPERTIES ('quality' = 'silver')
AS SELECT
  payment_id,
  event_ts,
  payment_type,
  debtor.account_id                      AS account_id,
  debtor.customer_id                     AS customer_id,
  creditor.payee_id                      AS payee_id,
  creditor.bank_name                     AS payee_bank_name,
  amount.value                           AS amount_gbp,
  amount.currency                        AS currency,
  reference,
  payee_added_ts,
  confirmation_of_payee.result           AS cop_result,
  channel_context.channel                AS channel,
  channel_context.device_id              AS device_id,
  channel_context.device_age_days        AS device_age_days,
  channel_context.session_duration_sec   AS session_duration_sec,
  channel_context.login_to_payment_sec   AS login_to_payment_sec,
  channel_context.on_active_call         AS on_active_call,
  _rescued_data,
  _source_file,
  _ingested_at
FROM STREAM(bronze_payments);

-- 1b) Quarantine: rows that failed hard rules, kept for payments-ops investigation (nothing is silently lost).
CREATE OR REFRESH STREAMING TABLE silver_payments_quarantine
COMMENT "Payments rejected by data-quality rules (null/negative amount, missing id/timestamp). Reviewed by Payments Operations."
TBLPROPERTIES ('quality' = 'quarantine')
AS SELECT
  payment_id, event_ts, debtor.customer_id AS customer_id, amount.value AS amount_gbp,
  CASE WHEN payment_id IS NULL THEN 'missing_payment_id'
       WHEN event_ts IS NULL THEN 'missing_event_ts'
       WHEN amount.value IS NULL THEN 'missing_amount'
       WHEN amount.value <= 0 THEN 'non_positive_amount'
       ELSE 'over_fps_limit' END AS quarantine_reason,
  _source_file, _ingested_at
FROM STREAM(bronze_payments)
WHERE payment_id IS NULL OR event_ts IS NULL OR amount.value IS NULL OR amount.value <= 0 OR amount.value > 1000000;

-- 2) De-duplicate at-least-once deliveries with AUTO CDC (SCD Type 1, keyed on payment_id).
CREATE OR REFRESH STREAMING TABLE silver_payments
COMMENT "One row per Faster Payment (deduplicated via AUTO CDC on payment_id). Authoritative payment fact for analytics and ML."
TBLPROPERTIES ('quality' = 'silver', 'delta.enableChangeDataFeed' = 'true');

CREATE FLOW silver_payments_dedupe AS AUTO CDC INTO silver_payments
FROM STREAM(silver_payments_validated)
KEYS (payment_id)
SEQUENCE BY _ingested_at
COLUMNS * EXCEPT (_rescued_data)
STORED AS SCD TYPE 1;

-- 3) Customers - PII protected by Unity Catalog column masks (functions created by 00_governance_setup).
--    Only members of account group `northbridge-pii-readers` see clear values. Derived, non-identifying
--    attributes (age, age band, postcode district) are computed here so downstream ML never needs raw PII.
CREATE OR REFRESH MATERIALIZED VIEW silver_customers (
  customer_id        STRING NOT NULL COMMENT 'Northbridge customer identifier (pseudonymous key)',
  full_name          STRING MASK ${catalog}.${fraud_schema}.mask_pii_string COMMENT 'PII - masked unless northbridge-pii-readers',
  date_of_birth      DATE   MASK ${catalog}.${fraud_schema}.mask_pii_date   COMMENT 'PII - year only unless northbridge-pii-readers',
  email              STRING MASK ${catalog}.${fraud_schema}.mask_pii_string COMMENT 'PII',
  mobile_phone       STRING MASK ${catalog}.${fraud_schema}.mask_pii_string COMMENT 'PII',
  postcode           STRING MASK ${catalog}.${fraud_schema}.mask_pii_string COMMENT 'PII - full postcode',
  postcode_district  STRING COMMENT 'Outward code only (e.g. LS12) - not identifying',
  region             STRING COMMENT 'UK region / nation',
  segment            STRING COMMENT 'Everyday / Premier / Student / Senior',
  age_years          INT    COMMENT 'Age at extract date',
  age_band           STRING COMMENT '18-24, 25-34, 35-49, 50-64, 65-74, 75+',
  vulnerability_flag BOOLEAN COMMENT 'FCA Consumer Duty - customer shows characteristics of vulnerability',
  tenure_months      INT,
  digital_active     BOOLEAN,
  extract_ts         TIMESTAMP,
  CONSTRAINT customer_pk PRIMARY KEY (customer_id)
)
COMMENT "Conformed customer dimension. Direct identifiers are column-masked by Unity Catalog."
TBLPROPERTIES ('quality' = 'silver', 'contains_pii' = 'true')
AS SELECT
  customer_id, full_name, date_of_birth, email, mobile_phone, postcode,
  split(postcode, ' ')[0] AS postcode_district,
  region, segment,
  CAST(floor(datediff(CAST(extract_ts AS DATE), date_of_birth) / 365.25) AS INT) AS age_years,
  CASE WHEN floor(datediff(CAST(extract_ts AS DATE), date_of_birth) / 365.25) < 25 THEN '18-24'
       WHEN floor(datediff(CAST(extract_ts AS DATE), date_of_birth) / 365.25) < 35 THEN '25-34'
       WHEN floor(datediff(CAST(extract_ts AS DATE), date_of_birth) / 365.25) < 50 THEN '35-49'
       WHEN floor(datediff(CAST(extract_ts AS DATE), date_of_birth) / 365.25) < 65 THEN '50-64'
       WHEN floor(datediff(CAST(extract_ts AS DATE), date_of_birth) / 365.25) < 75 THEN '65-74'
       ELSE '75+' END AS age_band,
  vulnerability_flag, tenure_months, digital_active, extract_ts
FROM bronze_customers
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY extract_ts DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_accounts (
  account_id          STRING NOT NULL,
  customer_id         STRING,
  sort_code           STRING MASK ${catalog}.${fraud_schema}.mask_pii_string COMMENT 'Account identifier - masked',
  account_number      STRING MASK ${catalog}.${fraud_schema}.mask_pii_string COMMENT 'Account identifier - masked',
  product             STRING,
  opened_date         DATE,
  current_balance_gbp DOUBLE,
  CONSTRAINT account_pk PRIMARY KEY (account_id)
)
COMMENT "Current accounts. Sort code / account number masked by Unity Catalog."
TBLPROPERTIES ('quality' = 'silver', 'contains_pii' = 'true')
AS SELECT account_id, customer_id, sort_code, account_number, product, opened_date, current_balance_gbp
FROM bronze_accounts
QUALIFY row_number() OVER (PARTITION BY account_id ORDER BY extract_ts DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_payees
COMMENT "Beneficiary dimension with receiving-PSP type and (where shared) receiving account age - key mule-account signals."
TBLPROPERTIES ('quality' = 'silver')
AS SELECT
  payee_id, payee_name, payee_category, payee_bank_name, payee_bank_type, payee_sort_code,
  payee_account_opened_date, intel_source IS NOT NULL AS intel_available
FROM bronze_payees
QUALIFY row_number() OVER (PARTITION BY payee_id ORDER BY extract_ts DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_scam_claims (
  CONSTRAINT claim_has_payment EXPECT (payment_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_outcome     EXPECT (outcome IN ('UPHELD', 'REJECTED'))
)
COMMENT "APP scam claim lines (one per scammed payment). UPHELD = reimbursed under PSR rules (cap GBP 85,000; 50:50 sending/receiving PSP)."
TBLPROPERTIES ('quality' = 'silver')
AS SELECT
  claim_id, customer_id, payment_id, reported_ts, scam_type_reported AS scam_type,
  claimed_amount_gbp, outcome, rejection_reason, reimbursed_amount_gbp, receiving_psp_contribution_gbp,
  reimbursed_amount_gbp - receiving_psp_contribution_gbp AS northbridge_net_cost_gbp,
  -- true APP scam = upheld, or rejected only for gross negligence (still a scam, just not reimbursable)
  (outcome = 'UPHELD' OR rejection_reason = 'GROSS_NEGLIGENCE') AS is_confirmed_app_scam
FROM bronze_scam_claims
QUALIFY row_number() OVER (PARTITION BY claim_id, payment_id ORDER BY _ingested_at DESC) = 1;
