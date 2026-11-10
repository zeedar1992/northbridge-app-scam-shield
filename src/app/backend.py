"""Data access for the Scam Shield app.

* Lakebase (Postgres)  - operational reads/writes: alert queue, case decisions, real-time feature lookups.
* SQL warehouse        - analytical KPIs from Unity Catalog gold / ML tables.
* Model Serving        - real-time APP-scam risk scoring (UC model @champion).
* Foundation Model API - GenAI customer warnings / follow-up drafts.
* Genie                - natural-language questions over the governed tables.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from databricks.sdk.service.sql import StatementState

w = WorkspaceClient()

CATALOG = os.getenv("NB_CATALOG", "serverless_stable_my49a8_catalog")
FRAUD = os.getenv("NB_FRAUD_SCHEMA", "northbridge_fraud")
ML = os.getenv("NB_ML_SCHEMA", "northbridge_ml")
OPS = os.getenv("NB_OPS_SCHEMA", "northbridge_ops")
OPS_HIST = os.getenv("NB_OPS_HISTORY_SCHEMA", "northbridge_ops_history")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
SERVING_ENDPOINT = os.getenv("NB_SERVING_ENDPOINT", "northbridge-scam-risk")
LLM_ENDPOINT = os.getenv("NB_LLM_ENDPOINT", "databricks-claude-sonnet-5-5")
GENIE_SPACE_ID = os.getenv("NB_GENIE_SPACE_ID", "")
LAKEBASE_ENDPOINT = os.getenv("NB_LAKEBASE_ENDPOINT", "projects/northbridge-scam-ops/branches/production/endpoints/primary")

# --------------------------------------------------------------------------------------------- Lakebase
_tok = {"value": None, "exp": 0.0}
_tok_lock = threading.Lock()


def _pg_password() -> str:
    with _tok_lock:
        if _tok["value"] is None or time.time() > _tok["exp"]:
            _tok["value"] = w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token
            _tok["exp"] = time.time() + 40 * 60          # OAuth tokens live 60 min; refresh at 40
        return _tok["value"]


class _TokenConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo: str = "", **kwargs):
        kwargs["password"] = _pg_password()
        return super().connect(conninfo, **kwargs)


def _pg_user() -> str:
    return os.getenv("PGUSER") or os.getenv("DATABRICKS_CLIENT_ID") or w.current_user.me().user_name


def _pg_host() -> str:
    return os.getenv("PGHOST") or w.postgres.get_endpoint(LAKEBASE_ENDPOINT).status.hosts.host


_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=f"host={_pg_host()} dbname={os.getenv('PGDATABASE', 'databricks_postgres')} user={_pg_user()} sslmode=require",
            connection_class=_TokenConnection, min_size=1, max_size=8, max_lifetime=30 * 60,
            kwargs={"autocommit": True, "row_factory": dict_row}, open=True)
    return _pool


@contextmanager
def pg():
    with pool().connection() as conn:
        yield conn


def pg_query(sql: str, params=None) -> list[dict]:
    with pg() as c:
        return c.execute(sql, params or ()).fetchall()


# --------------------------------------------------------------------------------------------- Warehouse
_cache: dict[str, tuple[float, list[dict]]] = {}


def sql(statement: str, ttl: int = 300) -> list[dict]:
    hit = _cache.get(statement)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE_ID, statement=statement, wait_timeout="50s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(1)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"SQL failed: {r.status.error.message if r.status.error else r.status.state}")
    cols = [c.name for c in r.manifest.schema.columns]
    rows = [dict(zip(cols, row)) for row in (r.result.data_array or [])] if r.result else []
    _cache[statement] = (time.time(), rows)
    return rows


# --------------------------------------------------------------------------------------------- GenAI
def llm(system: str, user: str, max_tokens: int = 1500) -> str:
    # Claude 5.5 spends part of max_tokens on internal reasoning: keep the budget generous or output is truncated
    resp = w.serving_endpoints.query(
        name=LLM_ENDPOINT, max_tokens=max_tokens,   # Claude 5.5 endpoints reject `temperature`
        messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=system), ChatMessage(role=ChatMessageRole.USER, content=user)])
    content = resp.choices[0].message.content
    if isinstance(content, list):   # Claude 5.5 returns content blocks (reasoning + text): keep only the text blocks
        content = "".join(c.get("text", "") if isinstance(c, dict) else str(getattr(c, "text", "")) for c in content
                          if (c.get("type") if isinstance(c, dict) else getattr(c, "type", "text")) == "text")
    return (content or "").strip()


# --------------------------------------------------------------------------------------------- Real-time scoring
RISK_REF = re.compile(r"safe account|security|hmrc|fraud|crypto|btc|invest|trading|platform|release fee|loan fee|customs|admin fee|prize|visa|medical|flight|love|deposit")


def build_features(cust: dict, payee: dict | None, rel: dict | None, p: dict, as_of: datetime) -> dict:
    """Mirror of gold_payment_features definitions (src/pipeline/transformations/03_gold.sql) for one new payment."""
    amount = float(p["amount_gbp"])
    prior = int(rel["prior_payments"]) if rel else 0
    if rel:
        mins_added = max((as_of - rel["first_paid_ts"]).total_seconds() / 60.0, 0.0) + 60 * 24 * 30
    else:
        mins_added = float(p.get("payee_added_minutes_ago", 5))
    opened = payee.get("payee_account_opened_date") if payee else None
    avg90 = float(cust["cust_avg_amount_90d"]) if cust.get("cust_avg_amount_90d") else None
    max90 = float(cust["cust_max_amount_90d"]) if cust.get("cust_max_amount_90d") else None
    hour = int(p.get("hour_of_day", as_of.hour))
    return {
        "amount_gbp": amount, "hour_of_day": hour, "minutes_since_payee_added": round(mins_added, 1),
        "prior_payments_to_payee": prior,
        "payee_account_age_days": (as_of.date() - opened).days if opened else None,
        "device_age_days": int(p.get("device_age_days", 400)), "session_duration_sec": int(p.get("session_duration_sec", 90)),
        "login_to_payment_sec": int(p.get("login_to_payment_sec", 40)),
        "cust_payments_24h": int(cust.get("cust_payments_24h") or 0),
        "cust_new_payee_payments_24h": int(cust.get("cust_new_payee_payments_24h") or 0),
        "cust_value_24h": float(cust.get("cust_value_24h") or 0), "cust_avg_amount_90d": avg90,
        "cust_payments_90d": int(cust.get("cust_payments_90d") or 0),
        "amount_to_cust_avg_ratio": round(amount / avg90, 3) if avg90 else None,
        "amount_to_cust_max_ratio": round(amount / max90, 3) if max90 else None,
        "payee_distinct_senders_7d": int(payee.get("payee_distinct_senders_7d") or 0) + (1 if prior == 0 else 0) if payee else 1,
        "payee_inbound_payments_7d": int(payee.get("payee_inbound_payments_7d") or 0) + 1 if payee else 1,
        "age_years": cust.get("age_years"), "tenure_months": cust.get("tenure_months"),
        "is_night": 0 <= hour <= 5, "is_new_payee": mins_added < 1440, "is_new_device": int(p.get("device_age_days", 400)) < 3,
        "on_active_call": bool(p.get("on_active_call", False)),
        "reference_risk_keyword": bool(RISK_REF.search((p.get("reference") or "").lower())),
        "vulnerability_flag": bool(cust.get("vulnerability_flag")), "digital_active": bool(cust.get("digital_active")),
        "payee_intel_available": bool(payee.get("intel_available")) if payee else False,
        "cop_result": p.get("cop_result", "MATCH"), "channel": p.get("channel", "MOBILE"),
        "payee_bank_type": (payee or {}).get("payee_bank_type") or p.get("payee_bank_type", "EMI"),
        "payee_category": (payee or {}).get("payee_category") or "PERSON", "payment_type": "FPS_SINGLE",
    }


def score(features: dict) -> dict:
    wire = {k: (float(v) if isinstance(v, bool) else v) for k, v in features.items()}   # model contract: booleans as 0/1 doubles
    r = w.serving_endpoints.query(name=SERVING_ENDPOINT, dataframe_records=[wire])
    out = r.predictions[0]
    out["reason_codes"] = json.loads(out["reason_codes"]) if isinstance(out.get("reason_codes"), str) else out.get("reason_codes")
    return out


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
