# Architecture: one integrated journey

```
                            ┌────────────────────────────── Unity Catalog (governance for every box below) ──────────────────────────────┐
                            │  schemas northbridge_raw / _fraud / _ml / _ops / _ops_history · column masks · governed tags · grants ·    │
                            │  automatic lineage · metric view · UC-registered model · inference tables · audit (system tables)          │
                            └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 RAW (synthetic)                LAKEFLOW (ingest + transform)                      ML + GenAI                          LAKEBASE (operational)            APP + GENIE
 ─────────────────              ─────────────────────────────                      ──────────                          ──────────────────────            ───────────
 UC Volume landing/             SDP pipeline (serverless)                          03 train  LightGBM → MLflow         synced tables (UC→PG)             Scam Shield App (FastAPI)
  payments_YYYY-MM-DD.json ──▶   bronze_* (Auto Loader, read_files)                    → UC model @champion  ─────┐     northbridge_ops.alert_queue ◀──┐   • Outcome (warehouse KPIs)
  customers/accounts/payees      silver_payments_validated (expectations)          04 batch score + reason codes  │     northbridge_ops.customer_profile │   • Analyst queue (PG r/w)
  scam_claims_YYYY-MM-DD.csv     silver_payments_quarantine                          + ai_query(Claude Haiku)     │     northbridge_ops.payee_profile    │   • Live payment check
        ▲                        silver_payments (AUTO CDC de-dup)                   → alert_queue (GenAI notes) ─┼──▶  northbridge_ops.customer_payee_… │       PG lookup → Serving → LLM
        │                        silver_customers/accounts (MASKED PII)            06 Model Serving endpoint ◀────┘                                     │   • Ask Genie (Conversation API)
 01 generator (job task)         gold_payment_features (point-in-time windows)       northbridge-scam-risk  ◀──────────────────── real-time score ────────┤
   incremental day files         gold_daily_fraud_kpis · gold_mule_watchlist        07 metric view + business case                                      │
                                                                                                               app writes (OLTP)                         │
                                                                                                               scam_ops.case_decisions / alert_status / ─┘
                                                                                                               payment_checks
                                                                                                                      │ Lakehouse Sync (CDC, SCD2)
                                                                                                                      ▼
                                                                                                               UC northbridge_ops_history.lb_*_history ──▶ Genie Agent + model feedback labels
```

## Orchestration
`resources/journey.job.yml`: one Lakeflow Job, nine tasks:

```
uc_governance_setup → land_raw_files → lakeflow_medallion_pipeline ─┬─▶ uc_tags_lineage_audit
                                                                    └─▶ train_scam_model ─┬─▶ deploy_model_serving
                                                                                          └─▶ score_and_genai_enrich ─┬─▶ publish_to_lakebase
                                                                                                                      └─▶ semantic_layer_business_case
```

## Deployed resources (bundle `northbridge-app-scam-shield`, target `fevm`)

| Stage | Resource | Name |
|---|---|---|
| Unity Catalog | schemas | `northbridge_raw`, `northbridge_fraud`, `northbridge_ml`, `northbridge_ops`, `northbridge_ops_history` |
| Unity Catalog | volume | `northbridge_raw.landing` |
| Unity Catalog | mask functions | `northbridge_fraud.mask_pii_string`, `mask_pii_date` |
| Lakeflow | SDP pipeline | `northbridge-app-fraud-medallion` (serverless, Photon) |
| Lakeflow | Job | `northbridge-app-scam-shield-journey` |
| ML | UC model | `northbridge_ml.app_scam_risk_model` (alias `champion`) |
| ML | Serving endpoint | `northbridge-scam-risk` (CPU Small, scale-to-zero, AI Gateway inference table) |
| GenAI | FMAPI | `databricks-claude-haiku-5-5` (batch), `databricks-claude-sonnet-5-5` (app) |
| Semantic | metric view | `northbridge_ml.app_scam_metrics` |
| Lakebase | project | `northbridge-scam-ops` (PG 17, 0.5–4 CU autoscaling) |
| Lakebase | synced tables | `northbridge_ops.alert_queue` (TRIGGERED), `customer_profile`, `payee_profile`, `customer_payee_history` (SNAPSHOT) |
| Lakebase | Lakehouse Sync | `scam_ops` → `northbridge_ops_history` |
| Genie | Agent | "Northbridge APP Scam Analyst" |
| App | Databricks App | `northbridge-scam-shield` |

## Security model
* App runs as its **own service principal** with least privilege, granted through app resources (warehouse CAN_USE, Lakebase CAN_CONNECT_AND_CREATE, serving CAN_QUERY, Genie CAN_RUN) plus explicit Postgres grants (SELECT on `northbridge_ops`, DML on `scam_ops`).
* PII is **masked in UC** for everyone outside `northbridge-pii-readers`, including the SP, Genie and data scientists. So the alert queue that lands in Lakebase only ever contains masked names (data minimisation into the operational store).
* Raw landing schema: owner-only. Consumers get `USE SCHEMA` + `SELECT` on silver/gold/ml/ops via bundle-declared grants to `account users`.
* Every model request/response is logged to the AI Gateway inference table in UC.
