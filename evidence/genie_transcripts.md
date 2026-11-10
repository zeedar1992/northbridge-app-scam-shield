# Genie Agent transcripts: "Northbridge APP Scam Analyst"

Captured 2026-11-10 09:18 UTC via the Genie Conversation API (`databricks genie start-conversation` / `create-message`), space `01f1dc9cb86f133c89e99c9b3ec0e2c9`.
Each answer shows Genie's text, the SQL it generated against the governed Unity Catalog tables/metric view, and the returned rows.

## Q1. Which scam type cost Northbridge the most in net reimbursement, and how much?

_You want to see the scam type that resulted in the highest net reimbursement cost for Northbridge, along with the total net reimbursement cost amount._

```sql
SELECT
  gold_payment_features.scam_type,
  SUM(gold_payment_features.northbridge_net_cost_gbp) AS net_reimbursement_cost_gbp
FROM serverless_stable_my49a8_catalog.northbridge_fraud.gold_payment_features
WHERE gold_payment_features.is_app_scam = 1
  AND gold_payment_features.scam_type IS NOT NULL
  AND gold_payment_features.northbridge_net_cost_gbp IS NOT NULL
GROUP BY gold_payment_features.scam_type
ORDER BY net_reimbursement_cost_gbp DESC
LIMIT 1
```

| scam_type | net_reimbursement_cost_gbp |
|---|---|
| investment | 2536616.1399999987 |

**Genie:** The scam type with the highest net reimbursement cost for Northbridge is **investment**, at **GBP 2,536,616.14**. In this result, **investment** is the top-cost scam type among confirmed APP scams with recorded net reimbursement cost.

## Q2.1. How much more scam value does the ML model catch than the legacy rules engine at the same alert budget?

_You want to see how much more scam value the ML model catches compared to the legacy rules engine when both operate at the same alert budget._

```sql
SELECT
  MAX(CASE WHEN `approach` ILIKE '%model%' OR `approach` ILIKE '%ml%' THEN `scam_value_caught_gbp` END) AS `ml_scam_value_caught_gbp`,
  MAX(CASE WHEN `approach` ILIKE '%legacy%' OR `approach` ILIKE '%rules%' THEN `scam_value_caught_gbp` END) AS `legacy_rules_scam_value_caught_gbp`,
  MAX(CASE WHEN `approach` ILIKE '%model%' OR `approach` ILIKE '%ml%' THEN `scam_value_caught_gbp` END)
    - MAX(CASE WHEN `approach` ILIKE '%legacy%' OR `approach` ILIKE '%rules%' THEN `scam_value_caught_gbp` END) AS `additional_scam_value_caught_gbp`
FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`model_evaluation`
```

| ml_scam_value_caught_gbp | legacy_rules_scam_value_caught_gbp | additional_scam_value_caught_gbp |
|---|---|---|
| 2250955.03 | 1387811.27 | 863143.7599999998 |

**Genie:** At the same alert budget, the **ML model** catches **GBP 2,250,955.03** of scam value versus **GBP 1,387,811.27** for the **legacy rules engine**, so the **ML model** catches **GBP 863,143.76 more**. In this result, the **ML model** captures about **62% more** scam value than the **legacy rules engine**.

## Q2.2. And what does that mean for precision - how many genuine customers do we hold per scam caught under each approach?

_You want to see how the legacy rules engine and the ML model compare in terms of precision and the number of genuine customers held per scam caught. The query shows the total alerts, scams caught, precision, and calculates how many genuine customers are held for each scam caught under each approach._

```sql
SELECT
  `approach`,
  `alerts`,
  `scams_caught`,
  `precision`,
  try_divide((`alerts` - `scams_caught`),CAST(`scams_caught` AS DOUBLE)) AS `genuine_customers_held_per_scam_caught`
FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`model_evaluation`
WHERE `approach` IS NOT NULL
  AND `alerts` IS NOT NULL
  AND `scams_caught` IS NOT NULL
  AND `precision` IS NOT NULL
ORDER BY `approach` ASC
```

| approach | alerts | scams_caught | precision | genuine_customers_held_per_scam_caught |
|---|---|---|---|---|
| ml_model_same_budget | 1533 | 482 | 0.3144 | 2.180497925311203 |
| rules_engine | 1533 | 104 | 0.0678 | 13.740384615384615 |

**Genie:** At the same alert volume of **1,533** holds, the **ML model** catches **482** scams with **31.44%** precision, which works out to about **2.18 genuine customers held per scam caught**. The **rules engine** catches **104** scams with **6.78%** precision, or about **13.74 genuine customers held per scam caught**. This means the ML approach is markedly more precise, holding far fewer genuine customers for each scam it identifies.

## Q3. Which receiving banks received the most confirmed scam value? Show bank type too.

_You're looking for a list of receiving banks ranked by the total confirmed scam value they received, including the type of each bank._

```sql
WITH `bank_scam_value` AS (
  SELECT
    `payee_bank_name`,
    `payee_bank_type`,
    SUM(`amount_gbp`) AS `confirmed_scam_value_gbp`
  FROM `serverless_stable_my49a8_catalog`.`northbridge_fraud`.`gold_payment_features`
  WHERE `is_app_scam` = 1
    AND `payee_bank_name` IS NOT NULL
    AND `payee_bank_type` IS NOT NULL
  GROUP BY
    `payee_bank_name`,
    `payee_bank_type`
),
`ranked_banks` AS (
  SELECT
    `payee_bank_name`,
    `payee_bank_type`,
    `confirmed_scam_value_gbp`,
    RANK() OVER (ORDER BY `confirmed_scam_value_gbp` DESC) AS `bank_rank`
  FROM `bank_scam_value`
)
SELECT
  `payee_bank_name`,
  `payee_bank_type`,
  `confirmed_scam_value_gbp`
FROM `ranked_banks`
ORDER BY `bank_rank` ASC, `payee_bank_name` ASC
```

| payee_bank_name | payee_bank_type | confirmed_scam_value_gbp |
|---|---|---|
| Monzo-like Neo | CHALLENGER | 2278426.8299999987 |
| Albion Bank | HIGH_STREET | 1511241.1000000008 |
| Brightpay EMI | EMI | 1403869.4900000019 |
| Crown & County | HIGH_STREET | 1265358.809999999 |
| Payflux EMI | EMI | 1137521.9100000004 |
| Caledonia Bank | HIGH_STREET | 799439.1700000005 |
| Starling-like Neo | CHALLENGER | 669223.8899999999 |
| Thames Mutual | BUILDING_SOCIETY | 448437.01000000007 |
| Northbridge Bank | HIGH_STREET | 324883.52000000014 |
| Unity Credit Union | CREDIT_UNION | 161599.9 |

**Genie:** Examples include:
- **Monzo-like Neo** (**CHALLENGER**) — **GBP 2,278,426.83**
- **Albion Bank** (**HIGH_STREET**) — **GBP 1,511,241.10**
- **Brightpay EMI** (**EMI**) — **GBP 1,403,869.49**
- **Crown & County** (**HIGH_STREET**) — **GBP 1,265,358.81**
- **Payflux EMI** (**EMI**) — **GBP 1,137,521.91**
Across the 10 banks shown, the highest confirmed scam value is at **Monzo-like Neo**, and **EMI** and **CHALLENGER** banks are prominent among the largest recipients.

## Q4. Show the top 5 mule watchlist accounts by number of distinct senders in 90 days

_You want to see the top 5 mule watchlist accounts ranked by the number of distinct senders who have sent payments to each account in the last 90 days._

```sql
WITH ranked_accounts AS (
  SELECT
    `payee_id`,
    `payee_bank_name`,
    `payee_bank_type`,
    `distinct_senders_90d`,
    RANK() OVER (ORDER BY `distinct_senders_90d` DESC) AS `sender_rank`
  FROM `serverless_stable_my49a8_catalog`.`northbridge_fraud`.`gold_mule_watchlist`
  WHERE `distinct_senders_90d` IS NOT NULL
    AND `payee_id` IS NOT NULL
)
SELECT
  `payee_id`,
  `payee_bank_name`,
  `payee_bank_type`,
  `distinct_senders_90d`
FROM ranked_accounts
WHERE `sender_rank` <= 5
ORDER BY `sender_rank` ASC, `distinct_senders_90d` DESC, `payee_id` ASC;
```

| payee_id | payee_bank_name | payee_bank_type | distinct_senders_90d |
|---|---|---|---|
| P2037843 | Northbridge Bank | HIGH_STREET | 11 |
| P2096518 | Albion Bank | HIGH_STREET | 10 |
| P2120183 | Brightpay EMI | EMI | 10 |
| P2012803 | Albion Bank | HIGH_STREET | 9 |
| P2023727 | Caledonia Bank | HIGH_STREET | 9 |
| P2058954 | Monzo-like Neo | CHALLENGER | 9 |
| P2096540 | Northbridge Bank | HIGH_STREET | 9 |

**Genie:** Because the query uses **rank <= 5**, it returns **7 accounts** due to ties rather than only 5. Notable accounts include:
- **P2037843** — **11** distinct senders in 90 days, **Northbridge Bank** (**HIGH_STREET**)
- **P2096518** — **10** distinct senders, **Albion Bank** (**HIGH_STREET**)
- **P2120183** — **10** distinct senders, **Brightpay EMI** (**EMI**)
- **P2012803** — **9** distinct senders, **Albion Bank** (**HIGH_STREET**)
- **P2023727** — **9** distinct senders, **Caledonia Bank** (**HIGH_STREET**)
Across these ranked accounts, the sender counts range from **9 to 11**, and **HIGH_STREET** banks make up most of the list.

## Q5. What share of impersonation scam value came from customers aged 65 or over?

_You want to know what percentage of the total impersonation scam value was from customers aged 65 or older._

```sql
SELECT try_divide(100 * SUM(CASE WHEN `age_band` IN ('65-74', '75+') THEN `amount_gbp` ELSE 0 END),SUM(`amount_gbp`)) AS `share_65_plus_pct`
FROM `serverless_stable_my49a8_catalog`.`northbridge_fraud`.`gold_payment_features`
WHERE `is_app_scam` = 1
  AND `scam_type` = 'impersonation'
  AND `age_band` IS NOT NULL
```

| share_65_plus_pct |
|---|
| 59.80215086074287 |

**Genie:** Customers in age bands **65-74** and **75+** accounted for **59.80%** of confirmed **impersonation** scam value, based on records with a non-null age band. In this result, customers aged **65 or over** made up the majority of impersonation scam value.

## Q6. How many alerts in the analyst queue are recommended HOLD_AND_CALL, and how many of those would the legacy rules have missed?

_You want to know the total number of alerts in the analyst queue that have a recommended action of HOLD_AND_CALL, and among those, how many would not have been flagged by the legacy rules engine._

```sql
SELECT COUNT(*) AS `hold_and_call_alerts`, SUM(CASE WHEN `legacy_rules_would_alert` = false THEN 1 ELSE 0 END) AS `missed_by_legacy_rules` FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`alert_queue` WHERE `recommended_action` = 'HOLD_AND_CALL'
```

| hold_and_call_alerts | missed_by_legacy_rules |
|---|---|
| 298 | 224 |

**Genie:** There are **298** alerts in the analyst queue with recommended action **HOLD_AND_CALL**. Of those **298** alerts, **224** alerts would have been missed by the legacy rules, which means most **HOLD_AND_CALL** recommendations are being picked up outside the legacy rule set.

## Q7. How many case decisions have analysts recorded so far and how much money was protected?

_You want to see the total number of case decisions recorded by analysts and the total amount of money protected based on those decisions._

```sql
SELECT COUNT(*) AS `case_decisions_recorded`, SUM(CASE WHEN `decision` IN ('CONFIRMED_SCAM_STOPPED', 'REFERRED_TO_POLICE') THEN COALESCE(`amount_protected_gbp`, 0) ELSE 0 END) AS `money_protected_gbp` FROM `serverless_stable_my49a8_catalog`.`northbridge_ops_history`.`lb_case_decisions_history` WHERE `_pg_change_type` = 'insert'
```

| case_decisions_recorded | money_protected_gbp |
|---|---|
| 16 | 147700.93 |

**Genie:** Analysts have recorded **16** case decisions so far, based on rows where `_pg_change_type` = `insert`. The total money protected from decisions **CONFIRMED_SCAM_STOPPED** and **REFERRED_TO_POLICE** is **GBP 147,700.93**.

## Q8. What is the net annual value in the business case and what are its main components?

_You want to see the net annual value from the business case along with its main components ranked by their absolute value._

```sql
WITH `net_row` AS ( SELECT 'net_annual_value' AS `row_type`, `sort_order`, `metric_key`, `metric`, `value`, `unit`, `basis` FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`business_case` WHERE ((`metric_key` ILIKE '%net%' AND `metric_key` ILIKE '%annual%' AND `metric_key` ILIKE '%value%') OR (`metric` ILIKE '%net%' AND `metric` ILIKE '%annual%' AND `metric` ILIKE '%value%')) ), `ranked_components` AS ( SELECT 'component' AS `row_type`, `sort_order`, `metric_key`, `metric`, `value`, `unit`, `basis`, ROW_NUMBER() OVER (ORDER BY ABS(`value`) DESC, `sort_order` ASC) AS `component_rank` FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`business_case` WHERE `unit` ILIKE '%gbp%' AND COALESCE(`is_total`, false) = false AND NOT ((`metric_key` ILIKE '%net%' AND `metric_key` ILIKE '%annual%' AND `metric_key` ILIKE '%value%') OR (`metric` ILIKE '%net%' AND `metric` ILIKE '%annual%' AND `metric` ILIKE '%value%')) ) SELECT `row_type`, `metric_key`, `metric`, `value`, `unit`, `basis` FROM ( SELECT `row_type`, `sort_order`, `metric_key`, `metric`, `value`, `unit`, `basis`, 0 AS `display_order` FROM `net_row` UNION ALL SELECT `row_type`, `sort_order`, `metric_key`, `metric`, `value`, `unit`, `basis`, `component_rank` AS `display_order` FROM `ranked_components` WHERE `component_rank` <= 5 ) `x` ORDER BY CASE WHEN `row_type` = 'net_annual_value' THEN 0 ELSE 1 END, `display_order` ASC, ABS(`value`) DESC, `sort_order` ASC
```

| row_type | metric_key | metric | value | unit | basis |
|---|---|---|---|---|---|
| net_annual_value | total_annual_value | Net annual value to Northbridge | 2652920.2421 | GBP | net reimbursement avoided + analyst capacity - run cost |
| component | attempted_scam_value | Implied attempted scam value (per year) | 1.80174667118E7 | GBP | losses / (1 - rules recall x 60% intervention success) |
| component | nb_losses_today | Northbridge APP scam losses today (per year) | 1.17182E7 | GBP | UK Finance 2024 APP losses GBP 450.7m x 2.6% PCA share (assumption) |
| component | customer_losses_prevented | Customer losses prevented (per year) | 3916636.9138 | GBP | attempted x (model recall - rules recall) x intervention success |
| component | annual_net_saving_gbp | Northbridge net reimbursement cost avoided | 1723320.2421 | GBP | prevented x 88% reimbursed (PSR) x 50% after receiving-PSP share |
| component | analyst_value_gbp | Value of analyst capacity released | 1109600.0 | GBP | hours x GBP 38/h loaded cost (redeploy to complex cases) |

**Genie:** The **net annual value to Northbridge** in the business case is **GBP 2,652,920.24**. Its main components shown here are **Northbridge net reimbursement cost avoided** of **GBP 1,723,320.24** and **value of analyst capacity released** of **GBP 1,109,600.00**; the basis states this is **net reimbursement avoided + analyst capacity - run cost**. 

Examples of related business-case values include:
- **Implied attempted scam value (per year):** **GBP 18,017,466.71**
- **Northbridge APP scam losses today (per year):** **GBP 11,718,200.00**
- **Customer losses prevented (per year):** **GBP 3,916,636.91**
- **Northbridge net reimbursement cost avoided:** **GBP 1,723,320.24**
- **Value of analyst capacity released:** **GBP 1,109,600.00**

**Genie:** Would you like to see all components regardless of size or only those with positive values instead?
