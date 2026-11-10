#!/usr/bin/env python3
"""Exercise the DEPLOYED Scam Shield app through its HTTP API and commit the responses as text evidence.

Auth: the caller's own short-lived Databricks CLI OAuth token, read from env APP_TOKEN (never written to disk).
    APP_TOKEN=$(databricks auth token --profile P | jq -r .access_token) python3 scripts/exercise_app.py <app_url>
"""
import json
import os
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = sys.argv[1].rstrip("/")
TOKEN = os.environ["APP_TOKEN"]
log = []


def call(method, path, body=None, note=""):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            status, data = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        status, data = e.code, {"error": e.read().decode()[:1000]}
    ms = round((time.perf_counter() - t) * 1000)
    log.append((method, path, body, status, ms, data, note))
    print(method, path, status, f"{ms} ms")
    return data


def trim(d, n=6):
    if isinstance(d, list):
        return [trim(x, n) for x in d[:n]] + ([f"... {len(d) - n} more"] if len(d) > n else [])
    if isinstance(d, dict):
        return {k: trim(v, n) for k, v in d.items()}
    return d


call("GET", "/api/health", note="Lakebase round-trip from the app container")
o = call("GET", "/api/outcome", note="Outcome view: UC tables via SQL warehouse + live Lakebase counters")
alerts = call("GET", "/api/alerts?status=OPEN&limit=10", note="Analyst queue read from Lakebase (synced alert_queue LEFT JOIN scam_ops.alert_status)")
missed = [a for a in alerts if not a.get("legacy_rules_would_alert")] or alerts
a1 = missed[0]["alert_id"]
call("GET", f"/api/alerts/{a1}", note="Alert detail incl. GenAI case note + customer profile (Lakebase)")
call("POST", f"/api/alerts/{a1}/claim", note="Analyst claims the alert (UPSERT scam_ops.alert_status)")
call("POST", f"/api/alerts/{a1}/draft-followup", note="Live GenAI (Claude Sonnet) customer message draft")
call("POST", f"/api/alerts/{a1}/decision", {"decision": "CONFIRMED_SCAM_STOPPED", "customer_contacted": True,
     "notes": "Customer confirmed caller claimed to be from Northbridge fraud team and asked to move money to a safe account. Payment stopped."},
     note="Decision + status written in ONE Lakebase transaction")
for a in alerts[1:4]:
    call("POST", f"/api/alerts/{a['alert_id']}/decision", {"decision": "RELEASED_AFTER_WARNING" if a["risk_band"] != "CRITICAL" else "REFERRED_TO_POLICE",
         "customer_contacted": True, "notes": "Evidence-capture run"}, note="More analyst decisions (feed Lakehouse Sync)")
ents = call("GET", "/api/sample-entities", note="Customers/payees for the live check (Lakebase)")
cust_v = ents["customers"][0]["customer_id"]; cust_y = ents["customers"][-1]["customer_id"]
mule = ents["payees"][0]["payee_id"]; biz = ents["payees"][-1]["payee_id"]
call("POST", "/api/check-payment", {"customer_id": cust_v, "payee_id": mule, "amount_gbp": 4800, "reference": "safe account", "channel": "MOBILE",
     "cop_result": "NO_MATCH", "on_active_call": True, "payee_added_minutes_ago": 6, "session_duration_sec": 420, "login_to_payment_sec": 260},
     note="Real-time check: coached 'safe account' payment to a watch-listed mule (Lakebase lookups -> Model Serving -> GenAI warning)")
call("POST", "/api/check-payment", {"customer_id": cust_y, "payee_id": biz, "amount_gbp": 1850, "reference": "builder stage 2", "channel": "WEB",
     "cop_result": "MATCH", "on_active_call": False, "payee_added_minutes_ago": 2880, "session_duration_sec": 75, "login_to_payment_sec": 30},
     note="Real-time check: genuine builder invoice")
call("POST", "/api/check-payment", {"customer_id": cust_y, "payee_id": mule, "amount_gbp": 350, "reference": "concert tickets", "channel": "MOBILE",
     "cop_result": "MATCH", "on_active_call": False, "payee_added_minutes_ago": 3, "session_duration_sec": 140, "login_to_payment_sec": 60},
     note="Real-time check: small, well-disguised purchase scam (genuine-looking behaviour). Honest residual-risk case: scored LOW and released; caught later via claims + mule watchlist feedback")
g = call("POST", "/api/genie", {"question": "Which scam type cost Northbridge the most in net reimbursement?"}, note="Ask Genie via the app (Conversation API)")
if g.get("conversation_id"):
    call("POST", "/api/genie", {"question": "And how much of that value did the legacy rules engine alert on?", "conversation_id": g["conversation_id"]},
         note="Genie follow-up in the same conversation")
call("GET", "/api/outcome", note="Outcome after decisions: live counters updated from Lakebase")

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
md = ["# Deployed app session: Northbridge APP Scam Shield", "",
      f"Captured {now} against **{BASE}** (Databricks App `northbridge-scam-shield`, running as its own service principal).",
      "Every call below is a real HTTPS request to the deployed app; responses are verbatim JSON (long lists trimmed). Generated by `scripts/exercise_app.py`.", "",
      "| # | call | HTTP | latency (ms) | what it proves |", "|---|---|---|---|---|"]
md += [f"| {i} | `{m} {p}` | {s} | {ms} | {n} |" for i, (m, p, b, s, ms, d, n) in enumerate(log, 1)]
for i, (m, p, b, s, ms, d, n) in enumerate(log, 1):
    md += ["", f"## {i}. `{m} {p}` · {s} · {ms} ms", "", f"_{n}_", ""]
    if b is not None:
        md += ["Request body:", "```json", json.dumps(b, indent=2), "```"]
    md += ["Response:", "```json", json.dumps(trim(d), indent=2, default=str)[:15000], "```"]
pathlib.Path("evidence/app_session.md").write_text("\n".join(md))
print("wrote evidence/app_session.md")
