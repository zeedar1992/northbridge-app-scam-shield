# Notebook sources

These `.py` files are the **source** notebooks deployed by the bundle and run as tasks of the Lakeflow Job `northbridge-app-scam-shield-journey`.

**Executed versions with their real cell outputs** (exported from job run 886593886805341) are in [`../../notebooks_executed/`](../../notebooks_executed/) as Jupyter `.ipynb` files that GitHub renders cell by cell, and as Markdown in [`../../evidence/job_run/`](../../evidence/job_run/).

| Source | Executed (with outputs) |
|---|---|
| `00_governance_setup.py` | [`00_uc_governance_setup.ipynb`](../../notebooks_executed/00_uc_governance_setup.ipynb) |
| `01_generate_raw_data.py` | [`01_land_raw_files.ipynb`](../../notebooks_executed/01_land_raw_files.ipynb) |
| `02_governance_catalog.py` | [`03_uc_tags_lineage_audit.ipynb`](../../notebooks_executed/03_uc_tags_lineage_audit.ipynb) |
| `03_train_scam_model.py` | [`04_train_scam_model.ipynb`](../../notebooks_executed/04_train_scam_model.ipynb) |
| `06_deploy_model_serving.py` | [`05_deploy_model_serving.ipynb`](../../notebooks_executed/05_deploy_model_serving.ipynb) |
| `04_score_and_genai_enrich.py` | [`06_score_and_genai_enrich.ipynb`](../../notebooks_executed/06_score_and_genai_enrich.ipynb) |
| `05_publish_to_lakebase.py` | [`07_publish_to_lakebase.ipynb`](../../notebooks_executed/07_publish_to_lakebase.ipynb) |
| `07_semantic_layer_and_business_case.py` | [`08_semantic_layer_business_case.ipynb`](../../notebooks_executed/08_semantic_layer_business_case.ipynb) |

The Lakeflow pipeline (`../pipeline/transformations/*.sql`) isn't a notebook. Its run log (rows per flow, expectations, events) is in [`../../evidence/pipeline_event_log.md`](../../evidence/pipeline_event_log.md).
