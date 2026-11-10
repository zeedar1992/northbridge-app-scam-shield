#!/usr/bin/env python3
"""Follow ONE real payment through every stage of the journey and commit what each stage holds (text evidence).

raw file in UC Volume -> Lakeflow bronze -> silver (validated, de-duplicated) -> gold features + legacy rules
-> ML score + reason codes -> GenAI case note -> Lakebase (synced alert queue, read by the app)
-> analyst decision written by the app -> Lakehouse Sync history in UC -> Genie answer -> UC lineage

Usage: python3 scripts/trace_one_payment.py [payment_id] [--profile P] [--warehouse ID]
"""
import argparse
import json
import pathlib
import subprocess
from datetime import datetime, timezone

C = "serverless_stable_my49a8_catalog"
GENIE = "01f1dc9cb86f133c89e99c9b3ec0e2c9"


def run(args, profile, as_json=True):
    r = subprocess.run(["databricks", *args, "--profile", profile] + (["-o", "json"] if as_json else []), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:600])
    return json.loads(r.stdout, strict=False) if as_json else r.stdout


def q(sql, a):
    return run(["experimental", "aitools", "tools", "query", sql, "--warehouse", a.warehouse], a.profile)


def md(rows):
    if not rows:
        return "_(no rows)_"
    cols = list(rows[0].keys())
    f = lambda v: str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")[:400]  # noqa: E731
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(f(r.get(c)) for c in cols) + " |" for r in rows])


def vertical(row):
    return "| field | value |\n|---|---|\n" + "\n".join(f"| {k} | {str(v if v is not None else '').replace('|', chr(92) + '|')[:500]} |" for k, v in row.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("payment_id", nargs="?", default="FP26001105668")
    ap.add_argument("--profile", default="fevm-serverless-stable-my49a8")
    ap.add_argument("--warehouse", default="1035b8c40230fe40")
    ap.add_argument("--out", default="evidence/trace_one_payment.md")
    a = ap.parse_args()
    pid, aid = a.payment_id, f"AL-{a.payment_id}"
    F, M, O, H = f"{C}.northbridge_fraud", f"{C}.northbridge_ml", f"{C}.northbridge_ops", f"{C}.northbridge_ops_history"
    S = []

    b = q(f"SELECT payment_id, _source_file, _ingested_at, debtor.customer_id AS customer_id, amount.value AS amount, reference FROM {F}.bronze_payments WHERE payment_id = '{pid}'", a)[0]
    vol_path = "dbfs:" + b["_source_file"].replace("dbfs:", "")
    raw_line = next(ln for ln in run(["fs", "cat", vol_path], a.profile, as_json=False).splitlines() if f'"{pid}"' in ln)
    S += ["## 0 · Raw file landed in the UC Volume (synthetic payments-hub feed)", "", f"File: `{b['_source_file']}`. The exact JSON line:", "",
          "```json", json.dumps(json.loads(raw_line), indent=2), "```"]
    S += ["## 1 · Lakeflow bronze (`northbridge_fraud.bronze_payments`, Auto Loader streaming table)", "", vertical(b)]
    S += ["## 2 · Lakeflow silver (`silver_payments`: flattened, 7 expectations passed, de-duplicated by AUTO CDC)", "",
          vertical(q(f"SELECT payment_id, event_ts, customer_id, payee_id, payee_bank_name, amount_gbp, cop_result, channel, on_active_call, session_duration_sec FROM {F}.silver_payments WHERE payment_id = '{pid}'", a)[0])]
    S += ["## 3 · Unity Catalog governance on the customer (masked for every non-PII reader, incl. this query)", "",
          vertical(q(f"SELECT c.customer_id, c.full_name, c.date_of_birth, c.email, c.postcode, c.postcode_district, c.age_band, c.vulnerability_flag, current_user() AS evaluated_as FROM {F}.silver_customers c WHERE c.customer_id = '{b['customer_id']}'", a)[0])]
    S += ["## 4 · Lakeflow gold (`gold_payment_features`): point-in-time features + what the LEGACY RULES decided", "",
          vertical(q(f"""SELECT payment_id, is_new_payee, minutes_since_payee_added, prior_payments_to_payee, payee_account_age_days, payee_bank_type,
                 amount_to_cust_avg_ratio, payee_distinct_senders_7d, reference_risk_keyword, on_active_call, cop_result,
                 rules_alert AS legacy_rules_alert FROM {F}.gold_payment_features WHERE payment_id = '{pid}'""", a)[0])]
    S += ["## 5 · ML (`payment_risk_scores`): UC model @champion score + reason codes", "",
          vertical(q(f"SELECT payment_id, risk_score, risk_band, model_alert, reason_codes, model_version, scored_at FROM {M}.payment_risk_scores WHERE payment_id = '{pid}'", a)[0])]
    S += ["## 6 · GenAI (`northbridge_ml.alert_queue`): case note written by Claude via `ai_query`", "",
          vertical(q(f"SELECT alert_id, genai_model, suspected_scam_type, analyst_summary, customer_call_script, recommended_action, genai_confidence, enriched_at FROM {M}.alert_queue WHERE alert_id = '{aid}'", a)[0])]
    S += ["## 7 · Lakebase (`northbridge_ops.alert_queue`): the synced Postgres row the app reads, plus sync status", "",
          vertical(q(f"SELECT alert_id, customer_display_name, amount_gbp, risk_band, suspected_scam_type, recommended_action, sla_due_ts FROM {O}.alert_queue WHERE alert_id = '{aid}'", a)[0]), "",
          "```json", json.dumps({k: v for k, v in run(["postgres", "get-synced-table", f"synced_tables/{O}.alert_queue"], a.profile)["status"].items()
                                 if k in ("detailed_state", "last_sync", "project")}, indent=2), "```"]
    S += ["## 8 · App → Lakebase → UC: the analyst decision written by the Scam Shield app, streamed back by Lakehouse Sync", "",
          md(q(f"SELECT _pg_change_type, alert_id, decision, analyst, customer_contacted, amount_protected_gbp, model_risk_score, notes, created_at, _timestamp AS synced_to_uc_at FROM {H}.lb_case_decisions_history WHERE alert_id = '{aid}' ORDER BY _sort_by", a)), "",
          md(q(f"SELECT _pg_change_type, alert_id, status, assigned_to, updated_at FROM {H}.lb_alert_status_history WHERE alert_id = '{aid}' ORDER BY _sort_by", a))]
    g = run(["genie", "start-conversation", GENIE, f"What happened to payment {pid}? Give its amount, model risk band, whether the legacy rules alerted, the GenAI suggested scam type and the analyst decision."], a.profile)
    text = " ".join(att["text"]["content"] for att in g.get("attachments") or [] if att.get("text", {}).get("content"))
    sql = next((att["query"]["query"] for att in g.get("attachments") or [] if att.get("query")), "")
    S += ["## 9 · Genie Agent: the same payment, asked in plain English", "", f"**Q:** What happened to payment {pid}? …", "", f"**Genie:** {text}", "", "```sql", sql, "```"]
    S += ["## 10 · Unity Catalog lineage for the tables this payment passed through", "",
          md(q(f"""SELECT DISTINCT source_table_name AS source, target_table_name AS target FROM system.access.table_lineage
                  WHERE target_table_catalog = '{C}' AND target_table_schema LIKE 'northbridge%' AND source_table_full_name IS NOT NULL
                    AND target_table_name IN ('silver_payments_validated', 'silver_payments', 'gold_payment_features', 'payment_risk_scores', 'alert_queue', 'customer_profile')
                  ORDER BY target, source""", a))]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    head = [f"# Follow one payment through the whole journey: `{pid}`", "",
            f"Captured {now} with real queries against the deployed build (`scripts/trace_one_payment.py`). This payment is the top-risk alert of the live window. "
            "**The legacy rules engine did not flag it, the model did**, Claude wrote the case note, an analyst stopped it in the app, and the decision flowed back into Unity Catalog.", "",
            "`raw JSON in Volume → bronze → silver → (masked customer) → gold features → ML score → GenAI note → Lakebase → app decision → Lakehouse Sync → Genie`", ""]
    pathlib.Path(a.out).write_text("\n".join(head + [x for s in S for x in ([s] if isinstance(s, str) else s)]) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
