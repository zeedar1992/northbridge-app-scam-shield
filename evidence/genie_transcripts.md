# Genie Agent transcripts: "Northbridge APP Scam Analyst"

Captured 2026-11-10 08:31 UTC via the Genie Conversation API (`databricks genie start-conversation` / `create-message`), space `01f1dc9cb86f133c89e99c9b3ec0e2c9`.
Each answer shows Genie's text, the SQL it generated against the governed Unity Catalog tables/metric view, and the returned rows.

## Q1. Which scam type cost Northbridge the most in net reimbursement, and how much?

_You want to see the scam type that resulted in the highest net reimbursement cost for Northbridge, along with the total net reimbursement cost for that scam type._

```sql
SELECT `scam_type`, SUM(`northbridge_net_cost_gbp`) AS `net_reimbursement_cost_gbp`
FROM `serverless_stable_my49a8_catalog`.`northbridge_fraud`.`gold_payment_features`
WHERE `is_app_scam` = 1
  AND `scam_type` IS NOT NULL
GROUP BY `scam_type`
ORDER BY `net_reimbursement_cost_gbp` DESC
LIMIT 1
```

| scam_type | net_reimbursement_cost_gbp |
|---|---|
| investment | 2536616.1399999987 |

**Genie:** The scam type with the **highest** net reimbursement cost for Northbridge is **investment**, with **GBP 2,536,616.14** in `northbridge_net_cost_gbp`. In the result shown, **investment** is the top scam type by net reimbursement cost.

## Q2.1. How much more scam value does the ML model catch than the legacy rules engine at the same alert budget?

_You want to see a comparison between the ML model and the legacy rules engine in terms of the number of alerts they generate and the total scam value they catch, as well as the additional scam value caught by the ML model at the same alert budget._

```sql
SELECT
  MAX(CASE WHEN LOWER(model_evaluation.approach) LIKE '%model%' THEN model_evaluation.alerts END) AS model_alerts,
  MAX(CASE WHEN LOWER(model_evaluation.approach) LIKE '%model%' THEN model_evaluation.scam_value_caught_gbp END) AS model_scam_value_caught_gbp,
  MAX(CASE WHEN LOWER(model_evaluation.approach) LIKE '%rules%' OR LOWER(model_evaluation.approach) LIKE '%legacy%' THEN model_evaluation.alerts END) AS legacy_alerts,
  MAX(CASE WHEN LOWER(model_evaluation.approach) LIKE '%rules%' OR LOWER(model_evaluation.approach) LIKE '%legacy%' THEN model_evaluation.scam_value_caught_gbp END) AS legacy_scam_value_caught_gbp,
  MAX(CASE WHEN LOWER(model_evaluation.approach) LIKE '%model%' THEN model_evaluation.scam_value_caught_gbp END)
    - MAX(CASE WHEN LOWER(model_evaluation.approach) LIKE '%rules%' OR LOWER(model_evaluation.approach) LIKE '%legacy%' THEN model_evaluation.scam_value_caught_gbp END) AS additional_scam_value_caught_gbp
FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`model_evaluation`
WHERE model_evaluation.approach IS NOT NULL
  AND model_evaluation.alerts IS NOT NULL
  AND model_evaluation.scam_value_caught_gbp IS NOT NULL
```

| model_alerts | model_scam_value_caught_gbp | legacy_alerts | legacy_scam_value_caught_gbp | additional_scam_value_caught_gbp |
|---|---|---|---|---|
| 1533 | 2250955.03 | 1533 | 1387811.27 | 863143.7599999998 |

**Genie:** At the same alert budget of **1,533 alerts**, the ML model catches **GBP 2,250,955.03** of scam value versus **GBP 1,387,811.27** for the legacy rules engine, so the ML model catches **GBP 863,143.76 more**. In this result, the ML model captures about **62% more** scam value than the legacy rules engine at the same alert volume.

## Q2.2. And what does that mean for precision - how many genuine customers do we hold per scam caught under each approach?

_You want to see how the legacy rules engine and the ML model compare in terms of precision and the number of genuine customers held per scam caught at the same alert budget._

```sql
SELECT
  `approach`,
  `alerts`,
  `scams_caught`,
  `precision`,
  (`alerts` - `scams_caught`) AS `genuine_customers_held`,
  try_divide((`alerts` - `scams_caught`),`scams_caught`) AS `genuine_customers_held_per_scam_caught`
FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`model_evaluation`
WHERE `approach` IS NOT NULL
  AND `alerts` IS NOT NULL
  AND `scams_caught` IS NOT NULL
  AND `precision` IS NOT NULL
ORDER BY `approach` ASC
```

| approach | alerts | scams_caught | precision | genuine_customers_held | genuine_customers_held_per_scam_caught |
|---|---|---|---|---|---|
| ml_model_same_budget | 1533 | 482 | 0.3144 | 1051 | 2.180497925311203 |
| rules_engine | 1533 | 104 | 0.0678 | 1429 | 13.740384615384615 |

**Genie:** At the same alert volume, the **ML model** is much more precise: it catches **482** scams with **31.44%** precision, which means about **2.18 genuine customers** are held for every scam caught. The **rules engine** catches **104** scams with **6.78%** precision, which means about **13.74 genuine customers** are held per scam caught. Across the 2 approaches shown, the ML model holds far fewer genuine customers for each scam it catches, making it the more efficient option at the same alert budget.

## Q3. Which receiving banks received the most confirmed scam value? Show bank type too.

_You're asking to see which receiving banks have received the highest total confirmed scam payments, including the type of each bank. The results are ranked from the highest to the lowest scam value received._

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
  `confirmed_scam_value_gbp`,
  `bank_rank`
FROM `ranked_banks`
ORDER BY
  `bank_rank` ASC,
  `confirmed_scam_value_gbp` DESC,
  `payee_bank_name` ASC;
```

| payee_bank_name | payee_bank_type | confirmed_scam_value_gbp | bank_rank |
|---|---|---|---|
| Monzo-like Neo | CHALLENGER | 2278426.8299999987 | 1 |
| Albion Bank | HIGH_STREET | 1511241.1000000008 | 2 |
| Brightpay EMI | EMI | 1403869.4900000019 | 3 |
| Crown & County | HIGH_STREET | 1265358.809999999 | 4 |
| Payflux EMI | EMI | 1137521.9100000004 | 5 |
| Caledonia Bank | HIGH_STREET | 799439.1700000005 | 6 |
| Starling-like Neo | CHALLENGER | 669223.8899999999 | 7 |
| Thames Mutual | BUILDING_SOCIETY | 448437.01000000007 | 8 |
| Northbridge Bank | HIGH_STREET | 324883.52000000014 | 9 |
| Unity Credit Union | CREDIT_UNION | 161599.9 | 10 |

**Genie:** Examples include:
- **Monzo-like Neo** — **CHALLENGER** — **GBP 2.28m** confirmed scam value
- **Albion Bank** — **HIGH_STREET** — **GBP 1.51m**
- **Brightpay EMI** — **EMI** — **GBP 1.40m**
- **Crown & County** — **HIGH_STREET** — **GBP 1.27m**
- **Payflux EMI** — **EMI** — **GBP 1.14m**

Across all **10** receiving banks shown, the highest confirmed scam value was **Monzo-like Neo** at **GBP 2.28m**, while **Unity Credit Union** was lowest at **GBP 0.16m**.

## Q4. Show the top 5 mule watchlist accounts by number of distinct senders in 90 days

_You want to see the top 5 mule watchlist accounts ranked by the number of distinct senders who paid them in the last 90 days. For each of these accounts, you want to know the account ID, the bank name and type, the count of distinct senders in 90 days, the total number of inbound payments in 90 days, and the total inbound payment value in GBP._

```sql
WITH ranked_accounts AS (
  SELECT
    `payee_id`,
    `payee_bank_name`,
    `payee_bank_type`,
    `distinct_senders_90d`,
    `inbound_payments_90d`,
    `inbound_value_gbp`,
    RANK() OVER (ORDER BY `distinct_senders_90d` DESC) AS `sender_rank`
  FROM `serverless_stable_my49a8_catalog`.`northbridge_fraud`.`gold_mule_watchlist`
  WHERE `distinct_senders_90d` IS NOT NULL
)
SELECT
  `payee_id`,
  `payee_bank_name`,
  `payee_bank_type`,
  `distinct_senders_90d`,
  `inbound_payments_90d`,
  `inbound_value_gbp`
FROM ranked_accounts
WHERE `sender_rank` <= 5
ORDER BY `sender_rank` ASC, `distinct_senders_90d` DESC, `payee_id` ASC;
```

| payee_id | payee_bank_name | payee_bank_type | distinct_senders_90d | inbound_payments_90d | inbound_value_gbp |
|---|---|---|---|---|---|
| P2037843 | Northbridge Bank | HIGH_STREET | 11 | 26 | 1669.46 |
| P2096518 | Albion Bank | HIGH_STREET | 10 | 41 | 3811.89 |
| P2120183 | Brightpay EMI | EMI | 10 | 23 | 195530.96 |
| P2012803 | Albion Bank | HIGH_STREET | 9 | 33 | 3433.2 |
| P2023727 | Caledonia Bank | HIGH_STREET | 9 | 29 | 3039.27 |
| P2058954 | Monzo-like Neo | CHALLENGER | 9 | 32 | 1938.06 |
| P2096540 | Northbridge Bank | HIGH_STREET | 9 | 23 | 6717.0 |

**Genie:** Because the query uses **rank <= 5**, it returns **7 accounts** due to ties rather than only 5. Some of the top mule watchlist accounts by distinct senders in the last 90 days are:
- **P2037843** — **11** distinct senders, **26** inbound payments, **£1,669.46** inbound value, **Northbridge Bank** (**HIGH_STREET**)
- **P2096518** — **10** distinct senders, **41** inbound payments, **£3,811.89** inbound value, **Albion Bank** (**HIGH_STREET**)
- **P2120183** — **10** distinct senders, **23** inbound payments, **£195,530.96** inbound value, **Brightpay EMI** (**EMI**)
- **P2012803** — **9** distinct senders, **33** inbound payments, **£3,433.20** inbound value, **Albion Bank** (**HIGH_STREET**)
- **P2023727** — **9** distinct senders, **29** inbound payments, **£3,039.27** inbound value, **Caledonia Bank** (**HIGH_STREET**)

Across the 7 returned accounts, distinct senders range from **9 to 11**, and **Brightpay EMI (P2120183)** stands out with by far the highest inbound value at **£195,530.96** despite not having the most senders.

## Q5. What share of impersonation scam value came from customers aged 65 or over?

_You're asking for the percentage of the total impersonation scam payment value that was made by customers aged 65 or older._

```sql
SELECT try_divide(100 * SUM(CASE WHEN `age_band` IN ('65-74', '75+') THEN `amount_gbp` ELSE 0 END),SUM(`amount_gbp`)) AS `share_65_plus_pct`
FROM `serverless_stable_my49a8_catalog`.`northbridge_fraud`.`gold_payment_features`
WHERE `is_app_scam` = 1
  AND `scam_type` = 'impersonation'
```

| share_65_plus_pct |
|---|
| 59.80215086074287 |

**Genie:** Customers in age bands **65-74** and **75+** accounted for **59.80%** of confirmed impersonation scam value. Based on the result shown, customers under 65 accounted for the remaining **40.20%**, so the majority of impersonation scam value came from customers aged 65 or over.

## Q6. How many alerts in the analyst queue are recommended HOLD_AND_CALL, and how many of those would the legacy rules have missed?

_You want to know the total number of alerts in the analyst queue that have a recommended action of HOLD_AND_CALL, and among those, how many would not have been flagged by the legacy rules engine._

```sql
SELECT COUNT(*) AS `hold_and_call_alerts`, SUM(CASE WHEN `legacy_rules_would_alert` = false THEN 1 ELSE 0 END) AS `hold_and_call_missed_by_legacy_rules` FROM `serverless_stable_my49a8_catalog`.`northbridge_ml`.`alert_queue` WHERE `recommended_action` = 'HOLD_AND_CALL'
```

| hold_and_call_alerts | hold_and_call_missed_by_legacy_rules |
|---|---|
| 299 | 224 |

**Genie:** There are **299** analyst-queue alerts with recommended action **HOLD_AND_CALL**. Of those **299** alerts, **224** would have been missed by the legacy rules, which means most **HOLD_AND_CALL** recommendations are being identified outside the legacy rule set.

**Genie:** Would you prefer to see the count based on the GenAI recommendation field instead of the recommended_action field?

## Q7. How many case decisions have analysts recorded so far and how much money was protected?

_You want to know the total number of case decisions recorded by analysts and the total amount of money protected based on those decisions._

```sql
SELECT COUNT(*) AS `case_decisions_recorded`, SUM(CASE WHEN `decision` IN ('CONFIRMED_SCAM_STOPPED', 'REFERRED_TO_POLICE') THEN COALESCE(`amount_protected_gbp`, 0) ELSE 0 END) AS `money_protected_gbp` FROM `serverless_stable_my49a8_catalog`.`northbridge_ops_history`.`lb_case_decisions_history` WHERE `_pg_change_type` = 'insert'
```

| case_decisions_recorded | money_protected_gbp |
|---|---|
| 12 | 108568.12 |

**Genie:** Analysts have recorded **12** case decisions so far, based on rows where `_pg_change_type` = `insert`. The total money protected from decisions **CONFIRMED_SCAM_STOPPED** and **REFERRED_TO_POLICE** is **GBP 108,568.12**.

## Q8. What is the net annual value in the business case and what are its main components?

_You want to see the net annual value from the business case along with its main components, including their metrics, values, units, and explanations._

```sql
WITH total_row AS (
  SELECT
    'net_annual_value' AS section,
    business_case.sort_order,
    business_case.metric_key,
    business_case.metric,
    business_case.value,
    business_case.unit,
    business_case.basis,
    business_case.is_total
  FROM serverless_stable_my49a8_catalog.northbridge_ml.business_case
  WHERE business_case.is_total = true
), component_rows AS (
  SELECT
    'component' AS section,
    business_case.sort_order,
    business_case.metric_key,
    business_case.metric,
    business_case.value,
    business_case.unit,
    business_case.basis,
    business_case.is_total
  FROM serverless_stable_my49a8_catalog.northbridge_ml.business_case
  WHERE business_case.is_total = false
    AND business_case.metric IS NOT NULL
    AND business_case.metric_key IS NOT NULL
)
SELECT
  section,
  sort_order,
  metric_key,
  metric,
  value,
  unit,
  basis,
  is_total
FROM total_row
UNION ALL
SELECT
  section,
  sort_order,
  metric_key,
  metric,
  value,
  unit,
  basis,
  is_total
FROM component_rows
ORDER BY CASE WHEN section = 'net_annual_value' THEN 0 ELSE 1 END, sort_order ASC
```

| section | sort_order | metric_key | metric | value | unit | basis | is_total |
|---|---|---|---|---|---|---|---|
| net_annual_value | 12 | total_annual_value | Net annual value to Northbridge | 2652920.2421 | GBP | net reimbursement avoided + analyst capacity - run cost | true |
| component | 1 | rules_value_recall | Scam value held by today's rules (hold-out test) | 0.5827 | pct | Measured: model_evaluation, same alert budget | false |
| component | 2 | model_value_recall | Scam value held by ML model (hold-out test) | 0.945 | pct | Measured: model_evaluation, same alert budget | false |
| component | 3 | nb_losses_today | Northbridge APP scam losses today (per year) | 1.17182E7 | GBP | UK Finance 2024 APP losses GBP 450.7m x 2.6% PCA share (assumption) | false |
| component | 4 | attempted_scam_value | Implied attempted scam value (per year) | 1.80174667118E7 | GBP | losses / (1 - rules recall x 60% intervention success) | false |
| component | 5 | customer_losses_prevented | Customer losses prevented (per year) | 3916636.9138 | GBP | attempted x (model recall - rules recall) x intervention success | false |
| component | 6 | annual_net_saving_gbp | Northbridge net reimbursement cost avoided | 1723320.2421 | GBP | prevented x 88% reimbursed (PSR) x 50% after receiving-PSP share | false |
| component | 7 | analyst_hours_saved | Analyst hours released (per year) | 29200.0 | hours | 1,200 holds/day x (11 -> 7 min) with GenAI case notes | false |
| component | 8 | analyst_value_gbp | Value of analyst capacity released | 1109600.0 | GBP | hours x GBP 38/h loaded cost (redeploy to complex cases) | false |
| component | 9 | genuine_holds_per_scam_rules | Genuine customers held per scam caught: rules | 13.7493 | ratio | Measured: 1/precision - 1 | false |
| component | 10 | genuine_holds_per_scam_model | Genuine customers held per scam caught: model | 2.1807 | ratio | Measured: Consumer Duty friction indicator | false |
| component | 11 | platform_run_cost | Platform run cost (per year) | -180000.0 | GBP | Estimate: serverless pipeline + Lakebase + serving + FMAPI + app | false |

**Genie:** The business case shows a **net annual value to Northbridge of GBP 2,652,920.24**. Its main components are **GBP 1,723,320.24** of net reimbursement cost avoided, **GBP 1,109,600.00** of analyst capacity released, and **GBP -180,000.00** of annual platform run cost; the largest positive contributor is reimbursement cost avoided.
