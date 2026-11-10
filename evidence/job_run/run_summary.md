# Job run 886593886805341: northbridge-app-scam-shield-journey

* Result: **SUCCESS**  ·  start 2026-11-10 09:02:09 UTC  ·  end 2026-11-10 09:17:22 UTC
* Job parameters: `{"catalog": "serverless_stable_my49a8_catalog", "through_date": "2026-11-08"}`
* Run page: https://fevm-serverless-stable-my49a8.cloud.databricks.com/?o=7474652570256692#job/982865610976081/run/886593886805341

| task | task run id | result | duration (s) | start (UTC) |
|---|---|---|---|---|
| uc_governance_setup | 291118273447486 | SUCCESS | 29 | 2026-11-10 09:02:09 UTC |
| land_raw_files | 247833414817654 | SUCCESS | 55 | 2026-11-10 09:02:38 UTC |
| lakeflow_medallion_pipeline | 261527030880964 | SUCCESS | 62 | 2026-11-10 09:03:34 UTC |
| train_scam_model | 138328630391401 | SUCCESS | 175 | 2026-11-10 09:04:37 UTC |
| uc_tags_lineage_audit | 475611867566209 | SUCCESS | 47 | 2026-11-10 09:04:37 UTC |
| deploy_model_serving | 863852793987238 | SUCCESS | 590 | 2026-11-10 09:07:32 UTC |
| score_and_genai_enrich | 674088591902543 | SUCCESS | 373 | 2026-11-10 09:07:32 UTC |
| publish_to_lakebase | 3172300787329 | SUCCESS | 47 | 2026-11-10 09:13:45 UTC |
| semantic_layer_business_case | 816349799366870 | SUCCESS | 33 | 2026-11-10 09:13:45 UTC |

Rows with the same task key are attempts. A later SUCCESS is a repair after a fix; see `docs/ai-assisted-build.md`.

