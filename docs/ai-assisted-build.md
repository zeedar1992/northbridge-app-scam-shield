# AI as a force multiplier: how this build was produced

**In one line:** one human (product owner and reviewer) and one AI coding agent (pair-engineer) took a one-paragraph brief to a deployed, governed, six-stage Databricks product in about 10 hours of wall-clock time. That included 6 job runs, 4 pipeline updates, 5 model versions, a Lakebase project, a Genie Agent, a deployed app and committed evidence. The agent wrote, deployed, ran and debugged everything. The human chose the problem, made the calls a customer would make, and owns the narrative.

| | |
|---|---|
| **Tool** | Claude Code (CLI coding agent, Claude Opus model) on the developer laptop |
| **Platform access** | Databricks CLI v1.21 with an OAuth profile (`fevm-serverless-stable-my49a8`); no PATs |
| **Knowledge** | Databricks Agent Skills plugin, loaded *before* writing code: `databricks-core`, `-dabs`, `-pipelines`, `-lakebase`, `-apps-python`, `-genie-agents`, `-metric-views`, `-ai-functions`; plus web search for industry facts |
| **Other agent tools** | Background monitors on job runs, a Chrome DevTools browser (blocked by Okta device policy, so it fell back to API tests), GitHub CLI |
| **Conversation / session ID** | `4d352f7c-9cb4-43ed-b074-1199d99dc2b1` (Claude Code session) |

## 1 · The brief (verbatim, from the human)
> *"Build a working prototype that solves a customer problem in a specific industry, as an end-to-end data journey starting from a raw dataset … Lakeflow · Unity Catalog · Lakebase · ML or Gen AI · Genie Agent · A Databricks app … deploy in https://fevm-serverless-stable-my49a8.cloud.databricks.com/ … be very specific, make sure all the requirements are met."*
> Follow-up decisions by the human when the agent asked: **industry = "something related to banking"**, **repo = public under `zeedar1992`**, **"yes, use my CLI token"** to exercise the deployed app.

## 2 · The working loop the agent followed
1. **Skills first, then design.** It loaded the relevant Databricks skills before writing code, so it used current product names and APIs (Lakeflow SDP, Lakebase Autoscaling `postgres` CLI, `postgres_projects` / `genie_spaces` bundle resources, Genie `serialized_space` v2, metric-view YAML 1.1) rather than stale memory.
2. **Probe the workspace before committing to a design.** It checked catalogs and privileges, warehouses, Lakebase, foundation-model endpoints, governed tag policies and existing projects, and adapted the design to what it found. One example: no `CREATE CATALOG` privilege, so it used dedicated `northbridge_*` schemas.
3. **Verify facts before they go in a business case.** Web search confirmed UK Finance's figure (£450.7m APP losses in 2024), the PSR £85k cap, and the PSR one-year update (88% of losses reimbursed by value).
4. **Test locally before burning cloud compute.** The data generator, and a proxy model to calibrate realism, ran locally first (1.13M rows in 22 s).
5. **Deploy → run → read the real error → fix → repair just the failed task** (Lakeflow Job *repair-run*), never re-running what had already passed.
6. **Evidence is a deliverable.** It wrote exporters that turn the executed job run, pipeline event log, live SQL, Genie and app sessions into committed text.
7. **Ask the human only for decisions that belong to the human:** the industry, the public repo, and permission to use a credential.

## 3 · Prompts that are *in the product* (verbatim)

**Batch case note: `ai_query` + Claude Haiku** (`src/notebooks/04_score_and_genai_enrich.py`)
```text
You are a senior APP-scam (authorised push payment) investigator at a UK retail bank. A payment has been held by the fraud model.
Write for a fraud analyst who must phone the customer within 4 hours. Use UK English, GBP, plain language. Never accuse the customer.
Return ONLY a minified JSON object (no markdown) with exactly these keys:
 "suspected_scam_type": one of purchase|impersonation|investment|romance|advance_fee|invoice_redirection|unclear,
 "analyst_summary": 2 sentences on why this looks risky, citing the strongest signals,
 "customer_call_script": 3 short open questions the analyst should ask (Consumer Duty compliant, no leading questions) ...,
 "recommended_action": one of HOLD_AND_CALL|WARN_AND_RELEASE|RELEASE,
 "confidence": one of low|medium|high
Payment facts: <amount, reference, channel, CoP, payee age, mule signals, call flag, age band, vulnerability, model score + reason codes>
```
**Live "pause and check" warning: Claude Sonnet, in the app** (`src/app/app.py`)
```text
You write the in-app 'pause and check' screen a UK bank shows before a risky bank transfer. Address the customer as 'you'.
Be specific to the scam pattern, calm, never accuse. 3 short sentences + one question. Max 70 words.
```
**Analyst follow-up draft: Claude Sonnet** (`src/app/app.py`)
```text
You write customer communications for a UK bank fraud team. Plain English, warm, never blame the customer, no links,
remind them the bank will never ask them to move money. Max 120 words.
```
**Genie Agent instructions** (`src/genie/build_genie_space.py`): 10 business rules covering the PSR reimbursement rules and 50:50 split, the label-lag caveat, the legacy-rule definition, the value-recall/precision definitions, mule signals, how to count analyst decisions from Lakehouse Sync history, and "never return direct identifiers". Plus 6 example SQLs, 4 join specs, 2 measures and 8 benchmark questions.

## 4 · Engineering prompts that shaped the build (agent-internal, paraphrased)
* *"Design the synthetic world so the model has to earn its uplift: genuine new-payee payments must sometimes look like scams (cars, builders, deposits), victims are coached to use innocent references, purchase scams are small, labels arrive late via claims and some are never reported."*
* *"This result is too good to be credible (ROC-AUC 0.9995, 100% recall). Find the giveaway features before anyone else does."* → it computed single-feature AUCs locally and made the data harder.
* *"Compare model and rules at the **same alert budget**: the fraud team's capacity is fixed."*
* *"Never extrapolate synthetic £ totals. Apply measured rates to published UK baselines, and make every assumption a row in a table."*
* *"Follow one payment through every stage and prove each hop with a query."* (that's `evidence/trace_one_payment.md`)

## 5 · Real failures the agent diagnosed and fixed (from real error output)
| # | Symptom (real) | Root cause | Fix |
|---|---|---|---|
| 1 | `PRINCIPAL_DOES_NOT_EXIST admins` | workspace-local group can't receive UC grants | raw schema owner-only |
| 2 | schemas created as `dev_<user>_…` | bundle `mode: development` prefixes names | removed dev mode |
| 3 | `UC_TAG_POLICY_VALUE_NOT_ALLOWED` | workspace has governed tag policies | reuse governed keys (`class.*`, `data_classification`, `system.certification_status`) |
| 4 | `Decimal is not JSON serializable` | Spark `round(x/60.0)` returns DECIMAL | cast numeric features to double |
| 5 | **ROC-AUC 0.9995, recall 100%** | synthetic scams too separable, rules too generous | harder, more realistic data; realistic 0.6% hold rate. Final PR-AUC ≈ 0.61 |
| 6 | MLflow schema enforcement on nullable booleans | implicit signature | explicit signature; booleans as 0/1 doubles everywhere |
| 7 | batch scoring didn't finish in 35 min | TreeSHAP on 1.1M rows ≈ 10¹² ops | explain only MEDIUM+ scores |
| 8 | `responseFormat` rejected by Claude | forced tool use not supported | prompted JSON + `from_json` |
| 9 | `does not support the parameter(s): temperature` | Claude 5.5 | removed `temperature` |
| 10 | JSON cut mid-sentence → null case notes | model reasons before answering; `max_tokens=600` too low | 2,000 tokens; failures logged, not fatal |
| 11 | app GenAI 500: `'list' object has no attribute 'strip'` | Claude returns content *blocks* | keep only text blocks |
| 12 | app / Genie 500: no `USE CATALOG` | app SP lacked catalog grant | grant in notebook + schema grants to SP in bundle |
| 13 | `Invalid cdf_config_id 'scam-ops-to-uc'` | Lakehouse Sync ids disallow hyphens | `scam_ops_to_uc` |
| 14 | browser login blocked ("Managed Chrome profile") | Okta device policy | asked the human for permission → API-level test with their CLI OAuth token |
| 15 | **reason code said "payment minutes after payee created" when the payee was 24 days old** (found by the one-payment trace) | static reason text ignored feature values | value-aware reason codes → model v5 |
| 16 | `SIGABRT` in one Lakebase task | transient platform error | job auto-retry succeeded; left visible in the run log |

## 6 · Patterns worth reusing
| Pattern | Where |
|---|---|
| Skills-first, probe-then-design | whole build |
| One bundle + one job DAG = one integrated journey (two-phase first deploy for objects the job creates) | `databricks.yml`, `resources/` |
| Genie-as-code with deterministic IDs (md5 of content) for stable git diffs | `src/genie/build_genie_space.py` |
| One pyfunc artefact (score + band + value-aware reasons) shared by batch, real-time and GenAI | `03_train_scam_model.py` |
| Docs rendered from measured numbers (no hand-typed KPIs) | `scripts/render_docs.py`, `docs/templates/` |
| Executed job run → `.ipynb` with outputs + Markdown; pipeline event log → Markdown | `scripts/export_run_evidence.py`, `scripts/export_pipeline_log.py` |
| Follow-one-record trace across every stage | `scripts/trace_one_payment.py` |

## 7 · What the human still had to own
* Picking a *specific* problem with a regulatory forcing function (PSR reimbursement), so value lands in the buyer's own KPIs.
* Judging credibility: rejecting a "perfect" model, insisting the business case uses rates rather than synthetic totals.
* Consent decisions: public repo, credential use.
* The narrative, the live demo and the objection handling (`docs/demo-script.md`). AI can draft it; only rehearsal makes it land.
