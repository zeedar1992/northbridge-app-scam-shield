# Job run 590537578235560: northbridge-app-scam-shield-journey

* Result: **SUCCESS**  ·  start 2026-11-10 00:22:10 UTC  ·  end 2026-11-10 08:59:19 UTC
* Job parameters: `{"catalog": "serverless_stable_my49a8_catalog", "through_date": "2026-11-08"}`
* Run page: https://fevm-serverless-stable-my49a8.cloud.databricks.com/?o=7474652570256692#job/982865610976081/run/590537578235560

| task | task run id | result | duration (s) | start (UTC) |
|---|---|---|---|---|
| uc_governance_setup | 225137203621598 | SUCCESS | 31 | 2026-11-10 00:22:10 UTC |
| land_raw_files | 1083923923384494 | SUCCESS | 49 | 2026-11-10 00:22:41 UTC |
| lakeflow_medallion_pipeline | 939281346104386 | SUCCESS | 93 | 2026-11-10 00:23:31 UTC |
| train_scam_model | 514710607757359 | SUCCESS | 173 | 2026-11-10 00:25:04 UTC |
| uc_tags_lineage_audit | 493688955409281 | SUCCESS | 53 | 2026-11-10 00:25:04 UTC |
| deploy_model_serving | 518133764689075 | SUCCESS | 650 | 2026-11-10 00:27:57 UTC |
| score_and_genai_enrich | 111047790233868 | SUCCESS | 313 | 2026-11-10 00:27:57 UTC |
| publish_to_lakebase | 319271002139431 | SUCCESS | 36 | 2026-11-10 00:33:10 UTC |
| semantic_layer_business_case | 371704668802180 | SUCCESS | 16 | 2026-11-10 00:33:10 UTC |
| score_and_genai_enrich | 302508417748477 | SUCCESS | 356 | 2026-11-10 08:16:57 UTC |
| publish_to_lakebase | 818180431527637 | SUCCESS | 40 | 2026-11-10 08:22:53 UTC |
| semantic_layer_business_case | 477017422827782 | SUCCESS | 30 | 2026-11-10 08:22:53 UTC |
| publish_to_lakebase | 471860505283008 | SUCCESS | 67 | 2026-11-10 08:46:44 UTC |
| semantic_layer_business_case | 1093849714504948 | SUCCESS | 50 | 2026-11-10 08:58:28 UTC |

Rows with the same task key are attempts. A later SUCCESS is a repair after a fix; see `docs/ai-assisted-build.md`.

