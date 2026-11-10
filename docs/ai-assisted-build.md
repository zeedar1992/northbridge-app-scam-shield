# AI as a force multiplier: how this build was produced

**Tool:** Claude Code (CLI agent, Claude Opus model) running against the Databricks CLI (v1.21) and workspace `fevm-serverless-stable-my49a8`, with the Databricks Agent Skills plugin loaded (`databricks-core`, `-dabs`, `-pipelines`, `-lakebase`, `-apps-python`, `-genie-agents`, `-metric-views`, `-ai-functions`).
**Human role:** product owner and reviewer. I chose the industry and problem (UK retail banking, APP-scam reimbursement liability), the GitHub destination, the business framing, and accepted or rejected design choices.
**AI role:** a pair-engineer that wrote the code, deployed it, ran it, read the failures and fixed them.

## Working pattern

1. **Brief → skills first.** The agent loaded the relevant Databricks skills *before* writing code, so it used current product names and APIs (Lakeflow SDP, Lakebase Autoscaling `postgres` CLI, `postgres_projects` bundle resource, Genie `serialized_space` v2, metric views YAML 1.1), not stale training memory.
2. **Probe the workspace before designing.** It checked catalogs, privileges, warehouses, Lakebase availability, foundation-model endpoints and governed tag policies, and adapted the design to what was there:
   * No `CREATE CATALOG` privilege → dedicated `northbridge_*` schemas in the existing catalog.
   * Lakehouse Sync needs a non-default-storage catalog → checked `storage_root` before relying on it.
   * Claude endpoints reject `ai_query(responseFormat=…)` → prompted JSON + `from_json` parsing, tested on the warehouse first.
3. **Verify industry facts on the web** before putting them in a business case: UK Finance 2025 report (£450.7m APP losses in 2024), the PSR £85k cap, and the PSR one-year update (88% of losses reimbursed by value).
4. **Local smoke tests before burning cloud compute.** The data generator ran locally first (1.13M rows, 22 s), which caught performance bugs (an O(n²) claim lookup, per-row payee lookups) before the first Databricks run.
5. **Deploy → run → read the error → fix → repair.** Every failure was diagnosed from real job output, not guessed. Real examples from this build:
   * `PRINCIPAL_DOES_NOT_EXIST admins` → workspace-local groups can't take UC grants; the raw schema became owner-only.
   * Bundle dev-mode prefixed schema names (`dev_<user>_…`) → removed `mode: development` so names match the code.
   * `UC_TAG_POLICY_VALUE_NOT_ALLOWED data_classification=restricted` → discovered the workspace tag policies and re-used the governed keys (`class.name`, `class.date_of_birth`, `system.certification_status`) instead of inventing new ones.
   * `Decimal is not JSON serializable` in the MLflow input example → cast numeric features to double at load time in both training and scoring.
   * **First model was "too good" (ROC-AUC 0.9995, 100% recall).** The agent flagged this as not credible, measured single-feature AUCs locally to find the giveaways, and made the synthetic world harder: coached victims, aged mule accounts, business-account mules, genuine new-payee payments made minutes after adding the payee, and a tighter, realistic legacy-rules budget. Final model: PR-AUC 0.61.
   * MLflow schema enforcement rejected nullable booleans → explicit model signature (booleans travel as 0/1 doubles) used by batch, serving and the app.
   * Batch scoring didn't finish in 35 min → diagnosed TreeSHAP cost (~10^12 ops on 1.1M rows); reason codes are now computed only for MEDIUM+ scores.
   * Claude 5.5 endpoints: `responseFormat` unsupported, `temperature` rejected, and `max_tokens=600` truncated JSON because the model reasons first. Each was found from real `genai_error` values and fixed (prompted JSON + `from_json`, no temperature, 2,000-token budget).
   * Claude Sonnet returned content *blocks* (reasoning + text) to the app → keep only text blocks.
   * App service principal lacked `USE CATALOG` on the shared catalog (Genie also runs as the SP) → grant added to the Lakebase notebook, schema grants to the SP added to the bundle.
   * Lakehouse Sync `cdf_config_id` rejects hyphens → `scam_ops_to_uc`.
   * A platform `SIGABRT` in one Lakebase task was retried automatically by the job and succeeded. Left as-is, visible in the run summary.
6. **Evidence as a first-class deliverable.** The agent wrote `scripts/export_run_evidence.py`, which turns each executed job task (code + real outputs) into Markdown, because the evaluator reads text only.

## Representative prompts (paraphrased from the session)

* "Build an end-to-end prototype for a specific industry problem: Lakeflow ingest → Unity Catalog → Lakebase → ML/GenAI → Genie → Databricks App. Make it banking. Deploy it to this workspace and commit text evidence that it ran."
* Agent-internal planning prompt it then followed: *"Design the synthetic data so the model has to earn its uplift: legitimate new-payee payments must look like scams sometimes (cars, builders), 35% of scam references are coached to look innocent, purchase scams are small. Otherwise the result is not credible."*
* GenAI prompt used in production (`04_score_and_genai_enrich.py`): senior APP-scam investigator persona, UK English, never accuse the customer, Consumer Duty-compliant open questions, strict JSON keys `suspected_scam_type / analyst_summary / customer_call_script / recommended_action / confidence`.

## Patterns worth re-using

| Pattern | Where |
|---|---|
| Skills-first, probe-then-design | whole build |
| Genie-as-code: deterministic IDs (md5 of content) for stable git diffs | `src/genie/build_genie_space.py` |
| One pyfunc artefact for batch + real-time + GenAI explanation | `03_train_scam_model.py` |
| Job-run → Markdown evidence exporter | `scripts/export_run_evidence.py` |
| Business case that applies measured rates to public baselines, with assumptions as table rows | `07_semantic_layer_and_business_case.py` |

## What I (the human) still had to own

* Choosing a *specific* problem with a regulatory forcing function (PSR reimbursement), so the value is in the buyer's own KPIs.
* Sanity-checking that numbers are defensible (the scam-enriched sample vs the bank-level business case).
* The narrative, the roleplay and the objection handling (`docs/demo-script.md`).
