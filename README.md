# Northbridge Bank · APP Scam Shield
### Stop the scam, not the customer: an end-to-end Databricks build for UK retail banking

> **Business outcome.** Since 7 Oct 2024 UK banks must reimburse authorised-push-payment (APP) scam victims, up to £85,000 per claim, with the cost split 50:50 between sending and receiving bank. That turns every scam that slips through into a direct P&L hit. On a hold-out test, Scam Shield intercepts **94% of scam value with the same number of payment holds** as today's rules engine (**58%**). The hit-rate goes from **6.8% to 31.4%**, so genuine customers held per scam caught fall from 13.7 to 2.2. Every alert arrives with a GenAI case note and a Consumer-Duty-safe call script.
>
> **Value for Northbridge** (fictional bank, 2.1M current accounts): **≈£2.7m net per year**, made up of **£1.7m** of net reimbursement cost avoided plus **29,200 analyst hours** released, after a £180,000 run cost. That's ROI ≈ 16× and payback ≈ 0.8 months. Every assumption is a row in [`northbridge_ml.business_case`](evidence/platform_queries.md#17-business-case-table).

| Who | What they get | KPI |
|---|---|---|
| **Executive sponsor**: CRO / COO | A forecastable, defensible APP reimbursement line; one governed number set for ExCo, the PSR and the FOS | Net reimbursement cost £, customer losses prevented £ |
| **Domain owner**: Head of Fraud Operations | Same team, more scam £ stopped, fewer false holds, pre-investigated cases | Value recall, precision, minutes per case, 4-hour SLA |

**Deck:** [`deck/northbridge-scam-shield-deck.pdf`](deck/northbridge-scam-shield-deck.pdf) ([markdown](deck/northbridge-scam-shield-deck.md)) · **Demo script + objection handling:** [`docs/demo-script.md`](docs/demo-script.md) · **Live app:** https://northbridge-scam-shield-7474652570256692.aws.databricksapps.com

---

## Execution evidence (text, committed)
The evaluator reads text, so everything below is real output, not screenshots.

| Evidence | File |
|---|---|
| Full job run: task states and durations of the integrated DAG | [`evidence/job_run/run_summary.md`](evidence/job_run/run_summary.md) |
| Every notebook as executed (code + outputs), one file per task | [`evidence/job_run/`](evidence/job_run/) |
| 21 live SQL checks: medallion row counts, DQ expectation metrics, quarantine, masks, tags, lineage, grants, model evaluation, GenAI notes, metric view, business case, Lakebase synced tables, Lakehouse Sync history, inference table | [`evidence/platform_queries.md`](evidence/platform_queries.md) |
| Genie Agent transcripts: questions → generated SQL → rows, incl. a follow-up | [`evidence/genie_transcripts.md`](evidence/genie_transcripts.md) |
| Deployed app exercised end-to-end: API responses for outcome, queue, decision write, live payment check (latency), GenAI draft, Genie | [`evidence/app_session.md`](evidence/app_session.md) |
| Incremental run: next business day lands, Auto Loader ingests only the new file | [`evidence/incremental_run.md`](evidence/incremental_run.md) |
| Headline numbers used in the deck (machine-generated from the run) | [`evidence/headline_numbers.json`](evidence/headline_numbers.json) |

---

## The integrated journey

```
Raw synthetic files ─▶ LAKEFLOW ─▶ UNITY CATALOG ─▶ ML + GenAI ─▶ LAKEBASE ─▶ DATABRICKS APP   (+ GENIE AGENT)
 payments JSON/day     Auto Loader   masks · tags ·   LightGBM →     synced     Outcome · Analyst queue ·
 claims CSV/day        SDP bronze→   lineage ·        UC @champion   tables +   Live payment check · Ask Genie
 customers/payees      silver→gold   metric view      + serving +    OLTP case       │
                       expectations                   ai_query       decisions ◀─────┘
                       AUTO CDC                       (Claude)          │ Lakehouse Sync (CDC)
                                                                        ▼
                                          UC history ─▶ Genie + retraining labels (feedback loop)
```

| Stage | Requirement | What was built | Where |
|---|---|---|---|
| 1 | **Lakeflow**: ingest raw data | Synthetic generator lands 89 daily JSON files + claims CSVs in a UC Volume. A **Lakeflow Spark Declarative Pipeline** (serverless) does Auto Loader bronze, 7 expectations, a quarantine table, **AUTO CDC** de-dup, masked silver and point-in-time gold features. A **Lakeflow Job** orchestrates all 9 stages. | `src/notebooks/01_generate_raw_data.py`, `src/pipeline/transformations/*.sql`, `resources/journey.job.yml` |
| 2 | **Unity Catalog**: govern it | 5 bundle-managed schemas with grants. **Column masks** on names, DOB, email, phone, postcode, sort code and account number (only `northbridge-pii-readers` see clear text). **Governed tags** (`class.*`, `data_classification`, `system.certification_status`). Lineage, a **metric view**, the UC-registered model, inference tables. | `src/notebooks/00_*`, `02_*`, `resources/unity_catalog.yml`, `07_*` |
| 3 | **Lakebase**: operational serving | Lakebase Autoscaling project (PG17). **Synced tables**: alert queue (TRIGGERED), customer/payee/relationship profiles (SNAPSHOT). App-owned OLTP tables (decisions, status, live checks). **Lakehouse Sync** streams decisions back to UC. | `resources/lakebase.yml`, `src/notebooks/05_publish_to_lakebase.py` |
| 4 | **ML / GenAI**: make it intelligent | Value-weighted **LightGBM** benchmarked against the rules at equal alert budget, a pyfunc with reason codes, registered in UC as `@champion`, served on **Model Serving**. **`ai_query` + Claude Haiku** writes case notes and call scripts in batch; **Claude Sonnet** drafts customer messages and the live "pause and check" warning in the app. | `03_*`, `04_*`, `06_*`, `src/app/backend.py` |
| 5 | **Genie Agent**: natural language | "Northbridge APP Scam Analyst", **deployed as code**: curated tables + metric view, business instructions (PSR rules), join specs, example SQL, measures, 8 benchmarks, PII columns excluded. | `src/genie/build_genie_space.py`, `resources/genie.yml` |
| 6 | **Databricks App**: surface it | FastAPI app on its own service principal with four views: **Outcome** (warehouse), **Analyst queue** (Lakebase r/w + GenAI), **Live payment check** (Lakebase → Serving → GenAI), **Ask Genie** (Conversation API). | `src/app/`, `resources/app.yml` |

Detail: [`docs/architecture.md`](docs/architecture.md) · How to deploy: [`docs/how-to-run.md`](docs/how-to-run.md)

---

## Results (hold-out 10–29 Oct 2026, same alert budget = 1,533 holds)

| | Legacy rules | ML model |
|---|---|---|
| Scam value intercepted | 58% | **94%** |
| Scams caught (count) | 17% | **78%** |
| Precision | 6.8% | **31.4%** |
| Holds needed to match today's catch | 1,533 | **168** (−89%) |

PR-AUC 0.609 · ROC-AUC 0.996. Honest caveat: the data is synthetic and scam-enriched (≈0.25% of payments) so the model has enough positives to learn from. That's why the business case applies measured **rates** to published UK baselines (UK Finance: £450.7m APP losses in 2024; PSR: 88% of losses reimbursed), never synthetic totals. The proposed next step is a 6-week shadow-mode pilot on Northbridge's own data.

| Scam type | Scam payments | Scam value | Rules value recall | Model value recall |
|---|---|---|---|---|
| investment | 117 | £1.4m | 69% | 98% |
| romance | 106 | £364,199 | 10% | 99% |
| impersonation | 74 | £327,568 | 83% | 90% |
| purchase | 240 | £136,381 | 9% | 71% |
| invoice_redirection | 24 | £94,032 | 78% | 75% |
| advance_fee | 56 | £19,596 | 0% | 69% |

---

## Decisions and trade-offs
The top five are below; the full table of 18 is in [`docs/decisions-and-tradeoffs.md`](docs/decisions-and-tradeoffs.md).
1. **Compare at the same alert budget, not AUC.** The fraud team's capacity is fixed, so "more £ caught with the same team?" is the buyer's question.
2. **Lakebase for the app, the warehouse for analytics.** Single-row reads and transactional writes (decision + status in one commit) vs scans. Synced tables and Lakehouse Sync remove ETL in both directions.
3. **Masks in UC, applied in the pipeline DDL.** PII protection travels to Genie, the LLM, the app SP and Lakebase. Features are derived from PII *inside* the governed pipeline.
4. **Batch GenAI (Haiku via `ai_query`) + interactive GenAI (Sonnet).** Cheap where it's bulk, higher quality where it's customer-facing. Prompted JSON + `from_json` because Claude endpoints reject `responseFormat` here.
5. **Feature parity by code (prototype) → online feature serving (production).** This is the explicit, known skew risk.

## AI as a force multiplier
Built with **Claude Code** plus the Databricks Agent Skills. Covered in [`docs/ai-assisted-build.md`](docs/ai-assisted-build.md): skills-first, probing the workspace before designing, verifying industry facts on the web, local smoke tests before cloud runs, diagnosing from real errors (14 real failures and their fixes are listed), and evidence as a first-class deliverable.

## Repository map
```
databricks.yml                 bundle: variables + target
resources/                     UC schemas+volume · SDP pipeline · journey job · Lakebase project · app · Genie Agent
src/notebooks/00..07           governance · data generator · UC tags/lineage · train · score+GenAI · Lakebase · serving · metric view+business case
src/pipeline/transformations/  01_bronze.sql · 02_silver.sql · 03_gold.sql
src/genie/                     Genie-as-code builder + serialized space JSON
src/app/                       FastAPI backend + static UI (Outcome · Queue · Live check · Genie)
scripts/                       evidence exporters, Genie transcripts, doc renderer
evidence/                      committed text evidence of execution
deck/                          business deck (PDF + markdown)
docs/                          architecture · decisions & trade-offs · AI-assisted build · demo script · how to run
```

*All data is synthetic. Northbridge Bank and all receiving banks are fictional. No customer data is used.*
