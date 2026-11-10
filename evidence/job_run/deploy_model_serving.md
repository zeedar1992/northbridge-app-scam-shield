# Task `deploy_model_serving` · notebook `06_deploy_model_serving` (executed, with outputs)

Executed by Lakeflow Job run 886593886805341 · task `deploy_model_serving` · task run 863852793987238 · result SUCCESS · 2026-11-10 09:07:32 UTC → 2026-11-10 09:17:22 UTC · source `src/notebooks/06_deploy_model_serving.py`

> Exported from the executed job run by `scripts/export_run_evidence.py`. Every output below is real.

# 06 · Real-time scoring: deploy `@champion` to a Model Serving endpoint

The same UC-registered pyfunc used for batch scoring is served behind a REST endpoint (scale-to-zero, CPU Small)
so the payments journey / Scam Shield app can score a payment **before it leaves the bank**.
Inference tables (AI Gateway) log every request/response to Unity Catalog for monitoring and audit.

```python
%pip install -q "databricks-sdk>=0.90" mlflow==3.4.0
%restart_python
```
**Output:**

```text
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
databricks-agents 1.11.0 requires mlflow-skinny<4,>=3.11.1, but you have mlflow-skinny 3.4.0 which is incompatible.
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("ml_schema", "northbridge_ml")
dbutils.widgets.text("serving_endpoint", "northbridge-scam-risk")
dbutils.widgets.text("app_name", "northbridge-scam-shield")
CATALOG, ML, EP, APP = (dbutils.widgets.get(k) for k in ["catalog", "ml_schema", "serving_endpoint", "app_name"])
MODEL = f"{CATALOG}.{ML}.app_scam_risk_model"

import json, time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (EndpointCoreConfigInput, ServedEntityInput, AiGatewayConfig,
                                            AiGatewayInferenceTableConfig, ServingEndpointAccessControlRequest,
                                            ServingEndpointPermissionLevel)
from mlflow import MlflowClient
import mlflow
mlflow.set_registry_uri("databricks-uc")
w = WorkspaceClient()
version = MlflowClient().get_model_version_by_alias(MODEL, "champion").version
print(f"deploying {MODEL} v{version} -> {EP}")
```
**Output:**

```text
deploying serverless_stable_my49a8_catalog.northbridge_ml.app_scam_risk_model v5 -> northbridge-scam-risk
```

```python
entity = ServedEntityInput(name="champion", entity_name=MODEL, entity_version=str(version), workload_size="Small", scale_to_zero_enabled=True)
existing = {e.name for e in w.serving_endpoints.list()}
if EP not in existing:
    w.serving_endpoints.create(name=EP, config=EndpointCoreConfigInput(name=EP, served_entities=[entity]),
                               ai_gateway=AiGatewayConfig(inference_table_config=AiGatewayInferenceTableConfig(
                                   enabled=True, catalog_name=CATALOG, schema_name=ML, table_name_prefix="scam_risk_serving")),
                               tags=[])
else:
    current = w.serving_endpoints.get(EP)
    served = [e.entity_version for e in (current.config.served_entities or [])] if current.config else []
    if str(version) not in served:
        w.serving_endpoints.update_config(name=EP, served_entities=[entity])
    else:
        print("endpoint already serves champion version", version)

deadline = time.time() + 45 * 60
while time.time() < deadline:
    s = w.serving_endpoints.get(EP)
    ready, upd = s.state.ready.value, s.state.config_update.value
    print(time.strftime("%H:%M:%S"), "ready:", ready, "config_update:", upd)
    if ready == "READY" and upd == "NOT_UPDATING":
        break
    if "FAILED" in upd:
        raise RuntimeError(f"endpoint update failed: {s.state}")
    time.sleep(60)
```
**Output:**

```text
09:08:17 ready: READY config_update: IN_PROGRESS
09:09:17 ready: READY config_update: IN_PROGRESS
09:10:17 ready: READY config_update: IN_PROGRESS
09:11:17 ready: READY config_update: IN_PROGRESS
09:12:17 ready: READY config_update: IN_PROGRESS
09:13:17 ready: READY config_update: IN_PROGRESS
09:14:17 ready: READY config_update: IN_PROGRESS
09:15:17 ready: READY config_update: IN_PROGRESS
09:16:17 ready: READY config_update: IN_PROGRESS
09:17:17 ready: READY config_update: NOT_UPDATING
```

```python
# grant the app's service principal CAN_QUERY (also declared as an app resource)
try:
    sp = w.apps.get(APP).service_principal_client_id
    ep_id = w.serving_endpoints.get(EP).id
    w.serving_endpoints.update_permissions(ep_id, access_control_list=[ServingEndpointAccessControlRequest(
        service_principal_name=sp, permission_level=ServingEndpointPermissionLevel.CAN_QUERY)])
    print("granted CAN_QUERY to", sp)
except Exception as e:
    print("grant skipped:", str(e)[:200])
```
**Output:**

```text
granted CAN_QUERY to fabee2fc-7b58-4ba9-9885-75ea672ff64c
```

### Smoke test: a coached "safe account" impersonation payment vs a genuine regular payment

```python
scam = {"amount_gbp": 4800.0, "hour_of_day": 14, "minutes_since_payee_added": 6.0, "prior_payments_to_payee": 0, "payee_account_age_days": 21,
        "device_age_days": 700, "session_duration_sec": 420, "login_to_payment_sec": 260, "cust_payments_24h": 0, "cust_new_payee_payments_24h": 0,
        "cust_value_24h": 0.0, "cust_avg_amount_90d": 85.0, "cust_payments_90d": 22, "amount_to_cust_avg_ratio": 56.5, "amount_to_cust_max_ratio": 9.6,
        "payee_distinct_senders_7d": 3, "payee_inbound_payments_7d": 4, "age_years": 78, "tenure_months": 240, "is_night": False, "is_new_payee": True,
        "is_new_device": False, "on_active_call": True, "reference_risk_keyword": True, "vulnerability_flag": True, "digital_active": True,
        "payee_intel_available": True, "cop_result": "NO_MATCH", "channel": "MOBILE", "payee_bank_type": "EMI", "payee_category": "PERSON",
        "payment_type": "FPS_SINGLE"}
genuine = {**scam, "amount_gbp": 62.0, "minutes_since_payee_added": 250000.0, "prior_payments_to_payee": 14, "payee_account_age_days": 2400,
           "session_duration_sec": 70, "login_to_payment_sec": 30, "amount_to_cust_avg_ratio": 0.73, "amount_to_cust_max_ratio": 0.12,
           "payee_distinct_senders_7d": 1, "payee_inbound_payments_7d": 1, "is_new_payee": False, "on_active_call": False,
           "reference_risk_keyword": False, "cop_result": "MATCH", "payee_bank_type": "HIGH_STREET", "payee_category": "BUSINESS", "age_years": 41,
           "vulnerability_flag": False}
to_wire = lambda r: {k: (float(v) if isinstance(v, bool) else v) for k, v in r.items()}   # booleans travel as 0/1 doubles
scam, genuine = to_wire(scam), to_wire(genuine)
lat = []
for _ in range(5):
    t = time.perf_counter(); r = w.serving_endpoints.query(name=EP, dataframe_records=[scam, genuine]); lat.append((time.perf_counter() - t) * 1000)
print(json.dumps(r.predictions, indent=2))
print(f"round-trip latency ms (2 records): min {min(lat):.0f}, median {sorted(lat)[2]:.0f}")
dbutils.notebook.exit(json.dumps({"endpoint": EP, "model_version": version, "predictions": r.predictions, "median_latency_ms": round(sorted(lat)[2], 1)}))
```

## Logged notebook exit value (`dbutils.notebook.exit`, from the Jobs API)

```json
{
  "endpoint": "northbridge-scam-risk",
  "model_version": "5",
  "predictions": [
    {
      "risk_score": 0.95561,
      "risk_band": "HIGH",
      "reason_codes": "[\"Payment made 6 minutes after the payee was created\", \"Payee type (personal vs business account)\", \"High payment value (GBP 4,800)\"]"
    },
    {
      "risk_score": 3e-06,
      "risk_band": "LOW",
      "reason_codes": "[]"
    }
  ],
  "median_latency_ms": 128.4
}
```