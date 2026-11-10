# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Publish to Lakebase (operational serving) + close the loop back to Unity Catalog
# MAGIC
# MAGIC | Direction | What | Mechanism |
# MAGIC |---|---|---|
# MAGIC | UC → Lakebase | `alert_queue` (GenAI-enriched analyst queue) | **Synced table, TRIGGERED** (CDF, incremental) |
# MAGIC | UC → Lakebase | `customer_profile`, `payee_profile`, `customer_payee_history` | **Synced tables, SNAPSHOT** (feature lookups for real-time scoring) |
# MAGIC | App → Lakebase | `scam_ops.case_decisions`, `scam_ops.alert_status`, `scam_ops.payment_checks` | OLTP inserts/updates from the Scam Shield app |
# MAGIC | Lakebase → UC | `northbridge_ops_history.lb_*_history` | **Lakehouse Sync** (CDC → SCD2 Delta) feeding model feedback + Genie |
# MAGIC
# MAGIC Why Lakebase and not the SQL warehouse for the app: analysts and the real-time payment check do **single-row
# MAGIC point lookups and writes** with sub-10ms latency and transactional semantics; the warehouse is built for scans.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.90" "psycopg[binary]>=3.2"
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("ml_schema", "northbridge_ml")
dbutils.widgets.text("ops_schema", "northbridge_ops")
dbutils.widgets.text("ops_history_schema", "northbridge_ops_history")
dbutils.widgets.text("lakebase_project", "northbridge-scam-ops")
dbutils.widgets.text("app_name", "northbridge-scam-shield")
CATALOG, ML, OPS, OPS_HIST, PROJECT, APP = (dbutils.widgets.get(k) for k in
    ["catalog", "ml_schema", "ops_schema", "ops_history_schema", "lakebase_project", "app_name"])

import json, time, statistics
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import SyncedTable, CdfConfig
w = WorkspaceClient()
BRANCH = f"projects/{PROJECT}/branches/production"
endpoint = next(iter(w.postgres.list_endpoints(BRANCH)))
db = next(d for d in w.postgres.list_databases(BRANCH) if d.status.postgres_database == "databricks_postgres")
HOST = endpoint.status.hosts.host
ME = w.current_user.me().user_name
print(f"endpoint={endpoint.name} host={HOST} database={db.name} user={ME}")

# COMMAND ----------

# MAGIC %md ## 1 · Synced tables (UC Delta → Postgres)

# COMMAND ----------

SYNCS = {   # target (in UC schema northbridge_ops == Postgres schema northbridge_ops): (source, pk, policy)
    "alert_queue":            (f"{CATALOG}.{ML}.alert_queue",            ["alert_id"],        "TRIGGERED"),
    "customer_profile":       (f"{CATALOG}.{ML}.customer_profile",       ["customer_id"],     "SNAPSHOT"),
    "payee_profile":          (f"{CATALOG}.{ML}.payee_profile",          ["payee_id"],        "SNAPSHOT"),
    "customer_payee_history": (f"{CATALOG}.{ML}.customer_payee_history", ["relationship_id"], "SNAPSHOT"),
}
spark.sql(f"ALTER TABLE {CATALOG}.{ML}.alert_queue SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")

def synced(name):
    try:
        return w.postgres.get_synced_table(f"synced_tables/{CATALOG}.{OPS}.{name}")
    except Exception:
        return None

for tgt, (src, pk, policy) in SYNCS.items():
    st = synced(tgt)
    if st is None:
        print(f"creating synced table {OPS}.{tgt} <- {src} [{policy}]")
        w.postgres.create_synced_table(
            synced_table=SyncedTable.from_dict({"spec": {
                "source_table_full_name": src, "primary_key_columns": pk, "scheduling_policy": policy,
                "branch": BRANCH, "postgres_database": "databricks_postgres", "create_database_objects_if_missing": True,
                "new_pipeline_spec": {"storage_catalog": CATALOG, "storage_schema": OPS}}}),
            synced_table_id=f"{CATALOG}.{OPS}.{tgt}")
    else:
        pid = st.status.pipeline_id
        print(f"refreshing synced table {OPS}.{tgt} via pipeline {pid}")
        try:
            w.pipelines.start_update(pid, full_refresh=(policy == "SNAPSHOT"))
        except Exception as e:
            print("  refresh skipped:", str(e)[:200])

# COMMAND ----------

deadline = time.time() + 40 * 60
pending = set(SYNCS)
while pending and time.time() < deadline:
    for tgt in sorted(pending):
        st = synced(tgt)
        state = st.status.detailed_state.value if st and st.status and st.status.detailed_state else "UNKNOWN"
        if state.startswith("SYNCED_TABLE_ONLINE") or state in ("SYNCED_TABLE_ONLINE",):
            print(f"{tgt}: {state}"); pending.discard(tgt)
        elif "FAILED" in state:
            raise RuntimeError(f"{tgt} sync failed: {st.status.message}")
    if pending:
        time.sleep(30)
print("still pending:", pending or "none")

# COMMAND ----------

# MAGIC %md ## 2 · App-owned OLTP tables, grants to the app service principal, indexes

# COMMAND ----------

import psycopg
def connect():
    tok = w.postgres.generate_database_credential(endpoint=endpoint.name).token
    return psycopg.connect(host=HOST, dbname="databricks_postgres", user=ME, password=tok, sslmode="require", autocommit=True)

DDL = """
CREATE SCHEMA IF NOT EXISTS scam_ops;
CREATE TABLE IF NOT EXISTS scam_ops.alert_status (
  alert_id      TEXT PRIMARY KEY,
  status        TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_REVIEW','CLOSED')),
  assigned_to   TEXT,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS scam_ops.case_decisions (
  decision_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  alert_id            TEXT NOT NULL,
  payment_id          TEXT NOT NULL,
  analyst             TEXT NOT NULL,
  decision            TEXT NOT NULL CHECK (decision IN ('CONFIRMED_SCAM_STOPPED','RELEASED_GENUINE','RELEASED_AFTER_WARNING','REFERRED_TO_POLICE')),
  customer_contacted  BOOLEAN NOT NULL DEFAULT false,
  amount_protected_gbp NUMERIC(14,2) NOT NULL DEFAULT 0,
  notes               TEXT,
  model_risk_score    DOUBLE PRECISION,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_case_decisions_alert ON scam_ops.case_decisions(alert_id);
CREATE TABLE IF NOT EXISTS scam_ops.payment_checks (
  check_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_id     TEXT NOT NULL,
  payee_id        TEXT,
  amount_gbp      NUMERIC(14,2) NOT NULL,
  reference       TEXT,
  channel         TEXT,
  on_active_call  BOOLEAN,
  risk_score      DOUBLE PRECISION,
  risk_band       TEXT,
  reason_codes    TEXT,
  action          TEXT,
  customer_warning TEXT,
  lookup_ms       DOUBLE PRECISION,
  scoring_ms      DOUBLE PRECISION,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE scam_ops.alert_status   REPLICA IDENTITY FULL;
ALTER TABLE scam_ops.case_decisions REPLICA IDENTITY FULL;
ALTER TABLE scam_ops.payment_checks REPLICA IDENTITY FULL;
"""
with connect() as conn:
    conn.execute(DDL)
    if not synced("alert_queue") is None:
        conn.execute(f"CREATE INDEX IF NOT EXISTS ix_alert_queue_risk ON {OPS}.alert_queue (risk_score DESC)")
    # app service principal (its Postgres role is created when the app gets the `postgres` resource)
    try:
        sp = w.apps.get(APP).service_principal_client_id
        for stmt in [f'GRANT USAGE ON SCHEMA {OPS} TO "{sp}"', f'GRANT SELECT ON ALL TABLES IN SCHEMA {OPS} TO "{sp}"',
                     f'ALTER DEFAULT PRIVILEGES IN SCHEMA {OPS} GRANT SELECT ON TABLES TO "{sp}"',
                     f'GRANT USAGE ON SCHEMA scam_ops TO "{sp}"',
                     f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA scam_ops TO "{sp}"',
                     f'ALTER DEFAULT PRIVILEGES IN SCHEMA scam_ops GRANT SELECT, INSERT, UPDATE ON TABLES TO "{sp}"']:
            conn.execute(stmt)
        print(f"granted app SP {sp} read on {OPS}.* and DML on scam_ops.*")
        spark.sql(f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{sp}`")      # catalog is not bundle-managed
        print(f"granted app SP {sp} USE CATALOG on {CATALOG} (schema grants are declared in the bundle)")
    except Exception as e:
        print("app SP grant skipped (deploy the app first):", str(e)[:300])
    rows = conn.execute(f"""
        SELECT table_schema, table_name, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text::bigint AS row_count
        FROM information_schema.tables WHERE table_schema IN ('{OPS}', 'scam_ops') AND table_type = 'BASE TABLE' ORDER BY 1, 2""").fetchall()
    print(f"{'schema':<18}{'table':<28}{'rows':>10}")
    for r in rows: print(f"{r[0]:<18}{r[1]:<28}{r[2]:>10,}")

# COMMAND ----------

# MAGIC %md ## 3 · Latency evidence: point lookups the real-time payment check performs

# COMMAND ----------

with connect() as conn:
    custs = [r[0] for r in conn.execute(f"SELECT customer_id FROM {OPS}.customer_profile ORDER BY random() LIMIT 200").fetchall()]
    payees = [r[0] for r in conn.execute(f"SELECT payee_id FROM {OPS}.payee_profile ORDER BY random() LIMIT 200").fetchall()]
    lat = []
    for c, p in zip(custs, payees):
        t = time.perf_counter()
        conn.execute(f"SELECT * FROM {OPS}.customer_profile WHERE customer_id = %s", (c,)).fetchone()
        conn.execute(f"SELECT * FROM {OPS}.payee_profile WHERE payee_id = %s", (p,)).fetchone()
        conn.execute(f"SELECT prior_payments FROM {OPS}.customer_payee_history WHERE relationship_id = %s", (f"{c}:{p}",)).fetchone()
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()
    latency = {"lookups": len(lat), "p50_ms_3_queries": round(statistics.median(lat), 2), "p95_ms_3_queries": round(lat[int(0.95 * len(lat)) - 1], 2)}
    q = conn.execute(f"""SELECT alert_id, amount_gbp, risk_band, suspected_scam_type, recommended_action
                         FROM {OPS}.alert_queue ORDER BY risk_score DESC LIMIT 5""").fetchall()
print(json.dumps(latency, indent=2))
for r in q: print(r)

# COMMAND ----------

# MAGIC %md ## 4 · Lakehouse Sync: Lakebase `scam_ops` → UC `northbridge_ops_history` (CDC, SCD2)

# COMMAND ----------

try:
    existing = list(w.postgres.list_cdf_configs(db.name))
except Exception:
    existing = []
if not any(c.postgres_schema == "scam_ops" for c in existing if getattr(c, "postgres_schema", None)):
    try:
        op = w.postgres.create_cdf_config(parent=db.name, cdf_config=CdfConfig(catalog=CATALOG, schema=OPS_HIST, postgres_schema="scam_ops"),
                                          cdf_config_id="scam_ops_to_uc")
        print("created CDF config:", op.wait() if hasattr(op, "wait") else op)
    except Exception as e:
        print("Lakehouse Sync create:", str(e)[:400])
try:
    for s in w.postgres.list_cdf_statuses(db.name):
        print(s)
except Exception as e:
    print("cdf statuses:", str(e)[:300])
# COMMAND ----------

dbutils.notebook.exit(json.dumps({"latency": latency, "synced_tables": list(SYNCS)}))
