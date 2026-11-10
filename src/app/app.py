"""Northbridge Bank - APP Scam Shield (Databricks App, FastAPI).

Business users: Head of Fraud (Outcome view), fraud analysts (Queue), payments product (Live check), everyone (Ask Genie).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import backend as b

log = logging.getLogger("scam-shield")
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Northbridge APP Scam Shield", version="1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

T = lambda s, t: f"{b.CATALOG}.{s}.{t}"     # noqa: E731


def _user(req: Request) -> str:
    return req.headers.get("x-forwarded-email") or req.headers.get("x-forwarded-preferred-username") or "analyst@northbridge.example"


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/health")
def health():
    t = time.perf_counter(); b.pg_query("SELECT 1")
    return {"lakebase_ms": round((time.perf_counter() - t) * 1000, 1), "serving_endpoint": b.SERVING_ENDPOINT,
            "llm": b.LLM_ENDPOINT, "genie_space": bool(b.GENIE_SPACE_ID)}


# ------------------------------------------------------------------------------------------ Outcome (exec)
@app.get("/api/outcome")
def outcome():
    ev = b.sql(f"SELECT * FROM {T(b.ML, 'model_evaluation')}")
    bc = b.sql(f"SELECT * FROM {T(b.ML, 'business_case')} ORDER BY sort_order")
    daily = b.sql(f"""SELECT event_date, payments, rules_alerts, confirmed_scam_payments, confirmed_scam_value_gbp,
                             scam_value_alerted_by_rules_gbp, northbridge_net_reimbursement_cost_gbp
                      FROM {T(b.FRAUD, 'gold_daily_fraud_kpis')} ORDER BY event_date""")
    mdl = b.sql(f"""SELECT event_date, round(sum(CASE WHEN model_alert AND is_app_scam = 1 THEN amount_gbp ELSE 0 END), 2) AS scam_value_alerted_by_model_gbp,
                           sum(CASE WHEN model_alert THEN 1 ELSE 0 END) AS model_alerts
                    FROM {T(b.ML, 'payment_risk_scores')} GROUP BY event_date ORDER BY event_date""")
    by_type = b.sql(f"SELECT * FROM {T(b.ML, 'model_recall_by_scam_type')} ORDER BY scam_value_gbp DESC")
    live = b.pg_query("""SELECT count(*) FILTER (WHERE created_at::date = now()::date) AS decisions_today,
                                coalesce(sum(amount_protected_gbp), 0) AS protected_gbp_total,
                                count(*) FILTER (WHERE decision = 'CONFIRMED_SCAM_STOPPED') AS scams_stopped,
                                count(*) AS decisions_total
                         FROM scam_ops.case_decisions""")[0]
    open_alerts = b.pg_query(f"""SELECT count(*) AS n FROM {b.OPS}.alert_queue q LEFT JOIN scam_ops.alert_status s USING (alert_id)
                                 WHERE coalesce(s.status, 'OPEN') <> 'CLOSED'""")[0]["n"]
    return {"evaluation": ev, "business_case": bc, "daily": daily, "model_daily": mdl, "by_type": by_type,
            "live": {**{k: float(v) for k, v in live.items()}, "open_alerts": open_alerts}}


# ------------------------------------------------------------------------------------------ Analyst queue (Lakebase)
@app.get("/api/alerts")
def alerts(status: str = "OPEN", limit: int = 50):
    rows = b.pg_query(f"""
        SELECT q.alert_id, q.payment_id, q.payment_ts, q.customer_id, q.customer_display_name, q.age_band, q.vulnerability_flag,
               q.amount_gbp, q.reference, q.channel, q.cop_result, q.is_new_payee, q.on_active_call, q.payee_name, q.payee_bank_name,
               q.payee_account_age_days, q.payee_distinct_senders_7d, q.risk_score, q.risk_band, q.reason_codes,
               q.suspected_scam_type, q.recommended_action, q.legacy_rules_would_alert, q.sla_due_ts,
               coalesce(s.status, 'OPEN') AS status, s.assigned_to
        FROM {b.OPS}.alert_queue q LEFT JOIN scam_ops.alert_status s USING (alert_id)
        WHERE (%(st)s = 'ALL' OR coalesce(s.status, 'OPEN') = %(st)s)
        ORDER BY q.risk_score DESC LIMIT %(lim)s""", {"st": status, "lim": limit})
    return rows


@app.get("/api/alerts/{alert_id}")
def alert_detail(alert_id: str):
    rows = b.pg_query(f"""SELECT q.*, coalesce(s.status, 'OPEN') AS status, s.assigned_to FROM {b.OPS}.alert_queue q
                          LEFT JOIN scam_ops.alert_status s USING (alert_id) WHERE q.alert_id = %s""", (alert_id,))
    if not rows:
        raise HTTPException(404, "alert not found")
    a = rows[0]
    a["decisions"] = b.pg_query("SELECT * FROM scam_ops.case_decisions WHERE alert_id = %s ORDER BY created_at DESC", (alert_id,))
    a["customer"] = (b.pg_query(f"SELECT * FROM {b.OPS}.customer_profile WHERE customer_id = %s", (a["customer_id"],)) or [None])[0]
    return a


class Decision(BaseModel):
    decision: str = Field(pattern="^(CONFIRMED_SCAM_STOPPED|RELEASED_GENUINE|RELEASED_AFTER_WARNING|REFERRED_TO_POLICE)$")
    customer_contacted: bool = True
    notes: str = ""


@app.post("/api/alerts/{alert_id}/decision")
def decide(alert_id: str, d: Decision, req: Request):
    a = b.pg_query(f"SELECT payment_id, amount_gbp, risk_score FROM {b.OPS}.alert_queue WHERE alert_id = %s", (alert_id,))
    if not a:
        raise HTTPException(404, "alert not found")
    a = a[0]
    protected = float(a["amount_gbp"]) if d.decision in ("CONFIRMED_SCAM_STOPPED", "REFERRED_TO_POLICE") else 0.0
    user = _user(req)
    with b.pg() as c, c.transaction():          # decision + status in ONE transaction (OLTP semantics)
        row = c.execute("""INSERT INTO scam_ops.case_decisions (alert_id, payment_id, analyst, decision, customer_contacted,
                                                                 amount_protected_gbp, notes, model_risk_score)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING decision_id, created_at""",
                        (alert_id, a["payment_id"], user, d.decision, d.customer_contacted, protected, d.notes, a["risk_score"])).fetchone()
        c.execute("""INSERT INTO scam_ops.alert_status (alert_id, status, assigned_to, updated_at) VALUES (%s, 'CLOSED', %s, now())
                     ON CONFLICT (alert_id) DO UPDATE SET status = 'CLOSED', assigned_to = EXCLUDED.assigned_to, updated_at = now()""",
                  (alert_id, user))
    return {"decision_id": row["decision_id"], "created_at": row["created_at"], "amount_protected_gbp": protected}


@app.post("/api/alerts/{alert_id}/claim")
def claim(alert_id: str, req: Request):
    b.pg_query("""INSERT INTO scam_ops.alert_status (alert_id, status, assigned_to) VALUES (%s, 'IN_REVIEW', %s)
                  ON CONFLICT (alert_id) DO UPDATE SET status = 'IN_REVIEW', assigned_to = EXCLUDED.assigned_to, updated_at = now()
                  RETURNING alert_id""", (alert_id, _user(req)))
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/draft-followup")
def draft_followup(alert_id: str):
    a = alert_detail(alert_id)
    facts = {k: a.get(k) for k in ["amount_gbp", "reference", "suspected_scam_type", "analyst_summary", "reason_codes", "age_band",
                                    "vulnerability_flag", "recommended_action"]}
    text = b.llm("You write customer communications for a UK bank fraud team. Plain English, warm, never blame the customer, "
                 "no links, remind them the bank will never ask them to move money. Max 120 words.",
                 f"Draft an SMS + in-app message to the customer whose payment we have paused. Facts: {json.dumps(facts, default=str)}")
    return {"draft": text, "model": b.LLM_ENDPOINT}


# ------------------------------------------------------------------------------------------ Live payment check
class PaymentCheck(BaseModel):
    customer_id: str
    payee_id: str | None = None
    amount_gbp: float = Field(gt=0)
    reference: str = ""
    channel: str = "MOBILE"
    cop_result: str = "MATCH"
    on_active_call: bool = False
    payee_added_minutes_ago: float = 5
    session_duration_sec: int = 90
    login_to_payment_sec: int = 40
    device_age_days: int = 400


@app.get("/api/sample-entities")
def sample_entities():
    custs = b.pg_query(f"""(SELECT customer_id, customer_display_name, age_band, vulnerability_flag, cust_avg_amount_90d FROM {b.OPS}.customer_profile
                            WHERE vulnerability_flag AND age_band = '75+' LIMIT 3)
                           UNION ALL (SELECT customer_id, customer_display_name, age_band, vulnerability_flag, cust_avg_amount_90d FROM {b.OPS}.customer_profile
                            WHERE age_band = '25-34' LIMIT 3)""")
    payees = b.pg_query(f"""(SELECT payee_id, payee_name, payee_bank_name, payee_bank_type, payee_distinct_senders_7d, on_mule_watchlist, payee_account_opened_date
                             FROM {b.OPS}.payee_profile WHERE on_mule_watchlist ORDER BY payee_distinct_senders_7d DESC LIMIT 3)
                            UNION ALL (SELECT payee_id, payee_name, payee_bank_name, payee_bank_type, payee_distinct_senders_7d, on_mule_watchlist, payee_account_opened_date
                             FROM {b.OPS}.payee_profile WHERE payee_category = 'BUSINESS' AND payee_bank_type = 'HIGH_STREET' AND NOT on_mule_watchlist LIMIT 3)""")
    return {"customers": custs, "payees": payees}


@app.post("/api/check-payment")
def check_payment(p: PaymentCheck):
    t0 = time.perf_counter()
    cust = b.pg_query(f"SELECT * FROM {b.OPS}.customer_profile WHERE customer_id = %s", (p.customer_id,))
    if not cust:
        raise HTTPException(404, "unknown customer")
    cust = cust[0]
    payee = b.pg_query(f"SELECT * FROM {b.OPS}.payee_profile WHERE payee_id = %s", (p.payee_id,)) if p.payee_id else []
    rel = b.pg_query(f"SELECT * FROM {b.OPS}.customer_payee_history WHERE relationship_id = %s", (f"{p.customer_id}:{p.payee_id}",)) if p.payee_id else []
    lookup_ms = (time.perf_counter() - t0) * 1000
    as_of = cust["as_of_ts"] if cust.get("as_of_ts") else datetime.now(timezone.utc)
    feats = b.build_features(cust, payee[0] if payee else None, rel[0] if rel else None, p.model_dump(), as_of)
    t1 = time.perf_counter()
    res = b.score(feats)
    scoring_ms = (time.perf_counter() - t1) * 1000
    band = res["risk_band"]
    action = {"CRITICAL": "HOLD_AND_CALL", "HIGH": "HOLD_AND_CALL", "MEDIUM": "DYNAMIC_WARNING"}.get(band, "RELEASE")
    warning, genai_ms = None, 0.0
    if action != "RELEASE":
        t2 = time.perf_counter()
        warning = b.llm("You write the in-app 'pause and check' screen a UK bank shows before a risky bank transfer. Address the customer "
                        "as 'you'. Be specific to the scam pattern, calm, never accuse. 3 short sentences + one question. Max 70 words.",
                        f"Payment GBP {p.amount_gbp:.2f}, reference '{p.reference}', risk reasons: {res['reason_codes']}. "
                        f"Customer on a phone call: {p.on_active_call}.", max_tokens=800)
        genai_ms = (time.perf_counter() - t2) * 1000
    row = b.pg_query("""INSERT INTO scam_ops.payment_checks (customer_id, payee_id, amount_gbp, reference, channel, on_active_call, risk_score,
                                                             risk_band, reason_codes, action, customer_warning, lookup_ms, scoring_ms)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING check_id""",
                     (p.customer_id, p.payee_id, p.amount_gbp, p.reference, p.channel, p.on_active_call, res["risk_score"], band,
                      json.dumps(res["reason_codes"]), action, warning, lookup_ms, scoring_ms))[0]
    return {"check_id": row["check_id"], **res, "action": action, "customer_warning": warning, "features": feats,
            "latency_ms": {"lakebase_lookups": round(lookup_ms, 1), "model_serving": round(scoring_ms, 1), "genai": round(genai_ms, 1),
                           "total": round((time.perf_counter() - t0) * 1000, 1)}}


# ------------------------------------------------------------------------------------------ Genie
class Ask(BaseModel):
    question: str
    conversation_id: str | None = None


@app.post("/api/genie")
def genie(q: Ask):
    if not b.GENIE_SPACE_ID:
        raise HTTPException(503, "Genie space not configured")
    if q.conversation_id:
        msg = b.w.genie.create_message_and_wait(b.GENIE_SPACE_ID, q.conversation_id, q.question)
    else:
        msg = b.w.genie.start_conversation_and_wait(b.GENIE_SPACE_ID, q.question)
    out = {"conversation_id": msg.conversation_id, "message_id": msg.message_id, "status": str(msg.status), "text": None, "sql": None,
           "description": None, "columns": [], "rows": []}
    for att in msg.attachments or []:
        if att.text and att.text.content:
            out["text"] = att.text.content
        if att.query:
            out["sql"], out["description"] = att.query.query, att.query.description
            res = b.w.genie.get_message_attachment_query_result(b.GENIE_SPACE_ID, msg.conversation_id, msg.message_id, att.attachment_id)
            sr = res.statement_response
            if sr and sr.manifest:
                out["columns"] = [c.name for c in sr.manifest.schema.columns]
                out["rows"] = (sr.result.data_array or [])[:50] if sr.result else []
    return out


@app.exception_handler(Exception)
async def on_error(_: Request, exc: Exception):
    log.exception("unhandled")
    return JSONResponse(status_code=500, content={"error": type(exc).__name__, "detail": str(exc)[:500]})
