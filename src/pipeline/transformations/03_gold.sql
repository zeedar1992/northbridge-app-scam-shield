-- =====================================================================================
-- GOLD  ·  ML-ready features, legacy-rules baseline, labels, business KPIs
-- =====================================================================================

-- Behavioural feature set, one row per payment. All windows look BACKWARDS only (no label leakage).
CREATE OR REFRESH MATERIALIZED VIEW gold_payment_features
COMMENT "One row per outbound Faster Payment with point-in-time behavioural features, the legacy rules-engine decision, and the (lagged) APP-scam label from claims. Training + scoring input for the scam-risk model."
TBLPROPERTIES ('quality' = 'gold', 'delta.enableChangeDataFeed' = 'true')
AS
WITH p AS (
  SELECT
    sp.*,
    unix_timestamp(sp.event_ts) AS ts_sec,
    a.product,
    c.age_years, c.age_band, c.vulnerability_flag, c.tenure_months, c.digital_active, c.region, c.segment,
    py.payee_category, py.payee_bank_type, py.payee_account_opened_date, py.intel_available
  FROM silver_payments sp
  LEFT JOIN silver_accounts  a  ON sp.account_id = a.account_id
  LEFT JOIN silver_customers c  ON sp.customer_id = c.customer_id
  LEFT JOIN silver_payees    py ON sp.payee_id = py.payee_id
),
w AS (
  SELECT
    p.*,
    -- customer velocity (prior 24h, excluding this payment)
    COUNT(*)        OVER (PARTITION BY customer_id ORDER BY ts_sec RANGE BETWEEN 86400 PRECEDING AND 1 PRECEDING)     AS cust_payments_24h,
    SUM(CASE WHEN payee_added_ts >= event_ts - INTERVAL 24 HOURS THEN 1 ELSE 0 END)
                    OVER (PARTITION BY customer_id ORDER BY ts_sec RANGE BETWEEN 86400 PRECEDING AND 1 PRECEDING)     AS cust_new_payee_payments_24h,
    SUM(amount_gbp) OVER (PARTITION BY customer_id ORDER BY ts_sec RANGE BETWEEN 86400 PRECEDING AND 1 PRECEDING)     AS cust_value_24h,
    -- customer baseline (prior 90 days)
    AVG(amount_gbp)    OVER (PARTITION BY customer_id ORDER BY ts_sec RANGE BETWEEN 7776000 PRECEDING AND 1 PRECEDING) AS cust_avg_amount_90d,
    MAX(amount_gbp)    OVER (PARTITION BY customer_id ORDER BY ts_sec RANGE BETWEEN 7776000 PRECEDING AND 1 PRECEDING) AS cust_max_amount_90d,
    COUNT(*)           OVER (PARTITION BY customer_id ORDER BY ts_sec RANGE BETWEEN 7776000 PRECEDING AND 1 PRECEDING) AS cust_payments_90d,
    -- payee / mule signals (prior 7 days incl. this payment): how many DIFFERENT customers paid this account
    size(collect_set(customer_id) OVER (PARTITION BY payee_id ORDER BY ts_sec RANGE BETWEEN 604800 PRECEDING AND CURRENT ROW)) AS payee_distinct_senders_7d,
    COUNT(*)           OVER (PARTITION BY payee_id ORDER BY ts_sec RANGE BETWEEN 604800 PRECEDING AND CURRENT ROW)            AS payee_inbound_payments_7d,
    -- relationship: how many times has this customer paid this payee before
    COUNT(*)           OVER (PARTITION BY customer_id, payee_id ORDER BY ts_sec RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_payments_to_payee
  FROM p
),
labels AS (
  SELECT payment_id,
         MAX(CASE WHEN is_confirmed_app_scam THEN 1 ELSE 0 END) AS is_app_scam,
         MAX(scam_type)               AS scam_type,
         MIN(reported_ts)             AS claim_reported_ts,
         SUM(reimbursed_amount_gbp)   AS reimbursed_amount_gbp,
         SUM(northbridge_net_cost_gbp) AS northbridge_net_cost_gbp
  FROM silver_scam_claims GROUP BY payment_id
)
SELECT
  w.payment_id, w.event_ts, CAST(w.event_ts AS DATE) AS event_date, w.customer_id, w.account_id, w.payee_id,
  w.amount_gbp, w.payment_type, w.channel, w.cop_result, w.reference, w.payee_bank_name, w.payee_bank_type, w.payee_category,
  w.region, w.segment, w.age_band, w.age_years, w.vulnerability_flag, w.tenure_months, w.digital_active, w.product,
  -- payment context features
  hour(w.event_ts)                                                          AS hour_of_day,
  hour(w.event_ts) BETWEEN 0 AND 5                                          AS is_night,
  (w.payee_added_ts >= w.event_ts - INTERVAL 24 HOURS)                      AS is_new_payee,
  round((unix_timestamp(w.event_ts) - unix_timestamp(w.payee_added_ts)) / 60.0, 1) AS minutes_since_payee_added,
  w.prior_payments_to_payee,
  datediff(CAST(w.event_ts AS DATE), w.payee_account_opened_date)           AS payee_account_age_days,
  w.intel_available                                                         AS payee_intel_available,
  w.device_age_days, (w.device_age_days < 3)                                AS is_new_device,
  w.session_duration_sec, w.login_to_payment_sec, w.on_active_call,
  regexp_like(lower(coalesce(w.reference, '')),
    'safe account|security|hmrc|fraud|crypto|btc|invest|trading|platform|release fee|loan fee|customs|admin fee|prize|visa|medical|flight|love|deposit') AS reference_risk_keyword,
  -- behavioural features
  coalesce(w.cust_payments_24h, 0)                                          AS cust_payments_24h,
  coalesce(w.cust_new_payee_payments_24h, 0)                                AS cust_new_payee_payments_24h,
  coalesce(w.cust_value_24h, 0)                                             AS cust_value_24h,
  w.cust_avg_amount_90d, w.cust_max_amount_90d, coalesce(w.cust_payments_90d, 0) AS cust_payments_90d,
  round(w.amount_gbp / nullif(w.cust_avg_amount_90d, 0), 3)                 AS amount_to_cust_avg_ratio,
  round(w.amount_gbp / nullif(w.cust_max_amount_90d, 0), 3)                 AS amount_to_cust_max_ratio,
  w.payee_distinct_senders_7d, w.payee_inbound_payments_7d,
  -- LEGACY RULES ENGINE (today's control at Northbridge) - the baseline the model must beat
  ( ((w.payee_added_ts >= w.event_ts - INTERVAL 24 HOURS) AND w.amount_gbp >= 3000)
    OR w.amount_gbp >= 15000
    OR (w.cop_result = 'NO_MATCH' AND w.amount_gbp >= 2000) )               AS rules_alert,
  -- LABEL (arrives late via claims)
  coalesce(l.is_app_scam, 0)                                                AS is_app_scam,
  l.scam_type, l.claim_reported_ts,
  coalesce(l.reimbursed_amount_gbp, 0)                                      AS reimbursed_amount_gbp,
  coalesce(l.northbridge_net_cost_gbp, 0)                                   AS northbridge_net_cost_gbp
FROM w LEFT JOIN labels l ON w.payment_id = l.payment_id;

-- Daily business KPIs for the Head of Fraud and the Genie Agent
CREATE OR REFRESH MATERIALIZED VIEW gold_daily_fraud_kpis
COMMENT "Daily APP-scam KPIs: volumes, legacy rules alert load and hit-rate, confirmed scam losses and PSR reimbursement cost (net of 50% receiving-PSP contribution)."
TBLPROPERTIES ('quality' = 'gold')
AS SELECT
  event_date,
  COUNT(*)                                                           AS payments,
  round(SUM(amount_gbp), 2)                                          AS payment_value_gbp,
  SUM(CASE WHEN is_new_payee THEN 1 ELSE 0 END)                      AS new_payee_payments,
  SUM(CASE WHEN rules_alert THEN 1 ELSE 0 END)                       AS rules_alerts,
  SUM(CASE WHEN rules_alert AND is_app_scam = 1 THEN 1 ELSE 0 END)   AS rules_true_positives,
  SUM(is_app_scam)                                                   AS confirmed_scam_payments,
  round(SUM(CASE WHEN is_app_scam = 1 THEN amount_gbp ELSE 0 END), 2) AS confirmed_scam_value_gbp,
  round(SUM(CASE WHEN is_app_scam = 1 AND rules_alert THEN amount_gbp ELSE 0 END), 2) AS scam_value_alerted_by_rules_gbp,
  round(SUM(reimbursed_amount_gbp), 2)                               AS reimbursed_gbp,
  round(SUM(northbridge_net_cost_gbp), 2)                            AS northbridge_net_reimbursement_cost_gbp
FROM gold_payment_features
GROUP BY event_date;

-- Mule-account watchlist: receiving accounts collecting money from many unrelated Northbridge customers
CREATE OR REFRESH MATERIALIZED VIEW gold_mule_watchlist
COMMENT "Receiving accounts that look like money mules: personal accounts opened in the last 180 days and paid by 3+ distinct Northbridge customers in any 7 days, or linked to a confirmed scam claim. Shared with receiving PSPs under inter-bank data sharing."
TBLPROPERTIES ('quality' = 'gold')
AS SELECT
  f.payee_id, f.payee_bank_name, f.payee_bank_type,
  MIN(f.payee_account_age_days)                 AS account_age_days_at_first_payment,
  MAX(f.payee_distinct_senders_7d)              AS max_distinct_senders_7d,
  COUNT(DISTINCT f.customer_id)                 AS distinct_senders_90d,
  COUNT(*)                                      AS inbound_payments_90d,
  round(SUM(f.amount_gbp), 2)                   AS inbound_value_gbp,
  SUM(f.is_app_scam)                            AS confirmed_scam_payments,
  round(SUM(CASE WHEN f.is_app_scam = 1 THEN f.amount_gbp ELSE 0 END), 2) AS confirmed_scam_value_gbp,
  MIN(f.event_ts) AS first_seen_ts, MAX(f.event_ts) AS last_seen_ts
FROM gold_payment_features f
WHERE f.payee_category = 'PERSON'
GROUP BY f.payee_id, f.payee_bank_name, f.payee_bank_type
HAVING (MAX(f.payee_distinct_senders_7d) >= 3 AND MIN(f.payee_account_age_days) <= 180) OR SUM(f.is_app_scam) > 0;
