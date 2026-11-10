# How to deploy and run

Prerequisites: Databricks CLI ≥ 1.21, a profile for the target workspace, a serverless SQL warehouse, Lakebase Autoscaling enabled, Foundation Model APIs (Claude) available.

```bash
# 0. configure the target in databricks.yml (profile, catalog, warehouse_id)

# 1. Phase 1: core resources (schemas, volume, Lakebase project, pipeline, job, app + its service principal)
databricks bundle validate --strict
databricks bundle deploy

# 2. Run the whole journey (≈35 min first time; most of it is Model Serving + synced-table provisioning)
databricks bundle run northbridge_journey
#    governance -> land raw files -> Lakeflow SDP -> UC tags/lineage -> train -> serve
#    -> score + GenAI -> Lakebase (synced tables, app tables, Lakehouse Sync) -> metric view + business case

# 3. Phase 2: the Genie Agent and app resources that reference job-created objects
mv resources/genie.yml.pending resources/genie.yml   # (already done in this repo)
databricks bundle deploy
databricks bundle run scam_shield_app                 # deploys + starts the app

# 4. Simulate the next business day arriving (incremental Auto Loader + triggered sync)
databricks bundle run northbridge_journey --params through_date=2026-11-08

# 5. Evidence
python3 scripts/export_run_evidence.py <job_run_id> --out evidence/job_run      # executed notebooks -> Markdown
python3 scripts/collect_platform_evidence.py                                    # 21 live SQL checks
python3 scripts/ask_genie_evidence.py <genie_space_id>                          # Genie transcripts
APP_TOKEN=$(databricks auth token --profile <P> | jq -r .access_token) \
  python3 scripts/exercise_app.py <app_url>                                     # deployed app API session
python3 scripts/render_docs.py <job_run_id>                                     # README / deck / demo script from measured numbers
```

Why two phases: Lakebase synced tables, the Genie space and the app's Genie/serving resources point at tables and endpoints that the job creates. The bundle can't reference them before they exist.

Re-running is idempotent: the generator only writes missing day files, the pipeline is incremental, the model registers a new version and moves `@champion`, the alert queue is MERGEd, and synced tables are refreshed rather than recreated.
