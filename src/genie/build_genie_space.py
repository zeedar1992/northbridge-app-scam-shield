"""Builds the serialized Genie Agent definition (Genie-as-code) -> src/genie/northbridge_scam.geniespace.json

Run:  python3 src/genie/build_genie_space.py   (the JSON is committed and deployed by resources/genie.yml)
IDs are deterministic (md5 of content) so re-builds are stable in git diffs.
"""
import hashlib
import json
import pathlib

C = "serverless_stable_my49a8_catalog"
F, M, H = f"{C}.northbridge_fraud", f"{C}.northbridge_ml", f"{C}.northbridge_ops_history"


def hid(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()


TABLES = {
    f"{F}.gold_daily_fraud_kpis": None,
    f"{F}.gold_payment_features": [
        {"column_name": "scam_type", "enable_entity_matching": True, "enable_format_assistance": True},
        {"column_name": "channel", "enable_entity_matching": True},
        {"column_name": "payee_bank_type", "enable_entity_matching": True},
        {"column_name": "payee_bank_name", "enable_entity_matching": True},
        {"column_name": "age_band", "enable_entity_matching": True},
        {"column_name": "region", "enable_entity_matching": True},
        {"column_name": "cop_result", "enable_entity_matching": True, "description": ["Confirmation of Payee outcome: MATCH, CLOSE_MATCH, NO_MATCH, UNAVAILABLE"]},
        {"column_name": "is_app_scam", "description": ["1 = confirmed APP scam (claim upheld, or rejected only for gross negligence); 0 = no confirmed scam (yet)"], "synonyms": ["fraud", "scam flag"]},
        {"column_name": "rules_alert", "description": ["Legacy rules engine would have held this payment"], "synonyms": ["rules flag", "legacy alert"]},
        {"column_name": "northbridge_net_cost_gbp", "description": ["Reimbursement paid minus the 50% receiving-PSP contribution"], "synonyms": ["net reimbursement cost", "liability"]},
    ],
    f"{F}.silver_scam_claims": [{"column_name": "scam_type", "enable_entity_matching": True}, {"column_name": "outcome", "enable_entity_matching": True}],
    f"{F}.gold_mule_watchlist": None,
    f"{F}.silver_customers": [{"column_name": "full_name", "exclude": True}, {"column_name": "email", "exclude": True},
                              {"column_name": "mobile_phone", "exclude": True}, {"column_name": "postcode", "exclude": True},
                              {"column_name": "date_of_birth", "exclude": True}],
    f"{M}.payment_risk_scores": [{"column_name": "risk_band", "enable_entity_matching": True}],
    f"{M}.alert_queue": [{"column_name": "suspected_scam_type", "enable_entity_matching": True},
                         {"column_name": "recommended_action", "enable_entity_matching": True}],
    f"{M}.model_evaluation": None,
    f"{M}.business_case": None,
    f"{H}.lb_case_decisions_history": [{"column_name": "decision", "enable_entity_matching": True}],
}

INSTRUCTIONS = [
    "You are the APP-scam analytics assistant for Northbridge Bank (fictional UK retail bank). All data is synthetic. Currency is GBP; use UK spelling.",
    "APP scam = authorised push payment scam: the customer is tricked into sending a Faster Payment to a criminal (often via a money-mule account).",
    "Confirmed scam payments: gold_payment_features.is_app_scam = 1. Scam value = SUM(amount_gbp) WHERE is_app_scam = 1. Labels arrive late via claims, so the last ~10 days (after 2026-10-29) are immature - say so when asked about recent losses.",
    "PSR reimbursement requirement (since 7 Oct 2024): victims are reimbursed up to GBP 85,000 per claim; cost is split 50:50 between the sending bank (Northbridge) and the receiving bank. Northbridge net cost = northbridge_net_cost_gbp.",
    "Legacy control = rules_alert (new payee and >= GBP 3,000, or >= GBP 15,000, or Confirmation of Payee NO_MATCH and >= GBP 2,000). ML control = payment_risk_scores.model_alert. Compare them at the same alert budget using model_evaluation (test window 2026-10-10..2026-10-29).",
    "Value recall = scam value held / total scam value. Precision = scam alerts / all alerts. Prefer the metric view app_scam_metrics with MEASURE() for these KPIs.",
    "Mule accounts: gold_mule_watchlist lists receiving accounts paid by many distinct Northbridge customers. Receiving bank type EMI / CHALLENGER are over-represented.",
    "Analyst decisions written by the Scam Shield app live in northbridge_ops_history.lb_case_decisions_history (Lakehouse Sync CDC history). Use rows where _pg_change_type = 'insert' to count decisions. CONFIRMED_SCAM_STOPPED and REFERRED_TO_POLICE mean money was protected (amount_protected_gbp).",
    "Never return direct identifiers (names, emails, phone numbers, postcodes, dates of birth); refer to customers by customer_id. Use age_band and vulnerability_flag for demographic questions.",
    "Business case figures (annual, GBP) are in business_case: use metric_key and value; the basis column explains each assumption.",
]

EXAMPLES = [
    ("What is the total confirmed APP scam value and net reimbursement cost by scam type?",
     f"SELECT scam_type, COUNT(*) AS scam_payments, ROUND(SUM(amount_gbp), 0) AS scam_value_gbp, ROUND(SUM(reimbursed_amount_gbp), 0) AS reimbursed_gbp, ROUND(SUM(northbridge_net_cost_gbp), 0) AS net_cost_gbp FROM {F}.gold_payment_features WHERE is_app_scam = 1 GROUP BY scam_type ORDER BY scam_value_gbp DESC"),
    ("How does the ML model compare with the legacy rules engine?",
     f"SELECT approach, alerts, scams_caught, scam_value_caught_gbp, precision, value_recall FROM {M}.model_evaluation ORDER BY approach"),
    ("Which receiving banks received the most confirmed scam value?",
     f"SELECT payee_bank_name, payee_bank_type, ROUND(SUM(amount_gbp), 0) AS scam_value_gbp, COUNT(DISTINCT payee_id) AS receiving_accounts FROM {F}.gold_payment_features WHERE is_app_scam = 1 GROUP BY payee_bank_name, payee_bank_type ORDER BY scam_value_gbp DESC"),
    ("Show daily rules alerts versus confirmed scams for October 2026",
     f"SELECT event_date, rules_alerts, rules_true_positives, confirmed_scam_payments, confirmed_scam_value_gbp FROM {F}.gold_daily_fraud_kpis WHERE event_date BETWEEN '2026-10-01' AND '2026-10-31' ORDER BY event_date"),
    ("What share of impersonation scam value came from customers aged 65 or over?",
     f"SELECT ROUND(SUM(CASE WHEN age_band IN ('65-74', '75+') THEN amount_gbp ELSE 0 END) / SUM(amount_gbp), 3) AS share_65_plus FROM {F}.gold_payment_features WHERE is_app_scam = 1 AND scam_type = 'impersonation'"),
    ("Model value recall by scam type in the test window",
     f"SELECT `Scam Type`, MEASURE(`Rules Value Recall`) AS rules_value_recall, MEASURE(`Model Value Recall`) AS model_value_recall FROM {M}.app_scam_metrics WHERE `Payment Date` BETWEEN '2026-10-10' AND '2026-10-29' AND `Scam Type` <> 'not a scam' GROUP BY ALL ORDER BY 2"),
]

SAMPLE_QUESTIONS = [
    "Which scam type cost us the most in net reimbursement?",
    "How much more scam value does the model catch than the rules?",
    "Top 10 mule-watchlist accounts by distinct senders",
    "How many alerts in the queue are recommended HOLD_AND_CALL?",
    "What is the annual net value in the business case?",
]

BENCHMARKS = [
    ("What was the total confirmed APP scam value in the test window 10-29 October 2026?",
     f"SELECT ROUND(SUM(amount_gbp), 2) AS scam_value_gbp FROM {F}.gold_payment_features WHERE is_app_scam = 1 AND event_date BETWEEN '2026-10-10' AND '2026-10-29'"),
    ("What value recall did the ML model achieve compared with the rules engine?",
     f"SELECT approach, value_recall FROM {M}.model_evaluation"),
    ("How many confirmed scam payments went to EMI receiving banks?",
     f"SELECT COUNT(*) AS scam_payments FROM {F}.gold_payment_features WHERE is_app_scam = 1 AND payee_bank_type = 'EMI'"),
    ("What is Northbridge's total net reimbursement cost by scam type?",
     f"SELECT scam_type, ROUND(SUM(northbridge_net_cost_gbp), 2) AS net_cost_gbp FROM {F}.gold_payment_features WHERE is_app_scam = 1 GROUP BY scam_type ORDER BY net_cost_gbp DESC"),
    ("How many payments did the legacy rules engine flag in total?",
     f"SELECT SUM(rules_alerts) AS rules_alerts FROM {F}.gold_daily_fraud_kpis"),
    ("How many alerts are in the analyst queue by recommended action?",
     f"SELECT recommended_action, COUNT(*) AS alerts FROM {M}.alert_queue GROUP BY recommended_action ORDER BY alerts DESC"),
    ("Which 5 mule watchlist accounts had the most distinct senders in 90 days?",
     f"SELECT payee_id, payee_bank_name, distinct_senders_90d, confirmed_scam_value_gbp FROM {F}.gold_mule_watchlist ORDER BY distinct_senders_90d DESC LIMIT 5"),
    ("What is the net annual value in the business case?",
     f"SELECT value FROM {M}.business_case WHERE metric_key = 'total_annual_value'"),
]

JOINS = [
    ("payment_risk_scores", f"{M}.payment_risk_scores", "gold_payment_features", f"{F}.gold_payment_features",
     "`payment_risk_scores`.`payment_id` = `gold_payment_features`.`payment_id`", "--rt=FROM_RELATIONSHIP_TYPE_ONE_TO_ONE--"),
    ("gold_payment_features", f"{F}.gold_payment_features", "silver_customers", f"{F}.silver_customers",
     "`gold_payment_features`.`customer_id` = `silver_customers`.`customer_id`", "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--"),
    ("silver_scam_claims", f"{F}.silver_scam_claims", "gold_payment_features", f"{F}.gold_payment_features",
     "`silver_scam_claims`.`payment_id` = `gold_payment_features`.`payment_id`", "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--"),
    ("alert_queue", f"{M}.alert_queue", "lb_case_decisions_history", f"{H}.lb_case_decisions_history",
     "`alert_queue`.`alert_id` = `lb_case_decisions_history`.`alert_id`", "--rt=FROM_RELATIONSHIP_TYPE_ONE_TO_MANY--"),
]


def build(include_history: bool = True) -> dict:
    tables = []
    for ident, cc in sorted(TABLES.items()):
        if not include_history and ident.startswith(H):
            continue
        t = {"identifier": ident}
        if cc:
            t["column_configs"] = sorted(cc, key=lambda c: c["column_name"])
        tables.append(t)
    joins = [j for j in JOINS if include_history or not j[3].startswith(H)]
    space = {
        "version": 2,
        "config": {"sample_questions": sorted([{"id": hid("sq", q), "question": [q]} for q in SAMPLE_QUESTIONS], key=lambda x: x["id"])},
        "data_sources": {"tables": tables, "metric_views": [{"identifier": f"{M}.app_scam_metrics"}]},
        "instructions": {
            "text_instructions": [{"id": hid("ti"), "content": [s + "\n" for s in INSTRUCTIONS]}],
            "example_question_sqls": sorted([{"id": hid("ex", q), "question": [q], "sql": [s]} for q, s in EXAMPLES], key=lambda x: x["id"]),
            "join_specs": sorted([{"id": hid("js", la, ra), "left": {"identifier": li, "alias": la}, "right": {"identifier": ri, "alias": ra},
                                   "sql": [cond, rt]} for la, li, ra, ri, cond, rt in joins], key=lambda x: x["id"]),
            "sql_snippets": {"measures": sorted([
                {"id": hid("m1"), "alias": "scam_value_gbp", "display_name": "Confirmed scam value (GBP)",
                 "sql": ["SUM(CASE WHEN gold_payment_features.is_app_scam = 1 THEN gold_payment_features.amount_gbp ELSE 0 END)"],
                 "synonyms": ["scam losses", "APP losses", "fraud value"]},
                {"id": hid("m2"), "alias": "net_reimbursement_cost_gbp", "display_name": "Net reimbursement cost (GBP)",
                 "sql": ["SUM(gold_payment_features.northbridge_net_cost_gbp)"], "synonyms": ["liability", "PSR cost"]},
            ], key=lambda x: x["id"])},
        },
        "benchmarks": {"questions": sorted([{"id": hid("bm", q), "question": [q], "answer": [{"format": "SQL", "content": [s]}]} for q, s in BENCHMARKS],
                                           key=lambda x: x["id"])},
    }
    return space


if __name__ == "__main__":
    import sys
    out = pathlib.Path(__file__).with_name("northbridge_scam.geniespace.json")
    out.write_text(json.dumps(build(include_history="--no-history" not in sys.argv), indent=2))
    print("wrote", out)
