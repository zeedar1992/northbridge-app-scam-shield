# Job run 121437029937396: northbridge-app-scam-shield-journey

* Result: **SUCCESS**  ·  start 2026-11-09 23:27:14 UTC  ·  end 2026-11-10 00:20:49 UTC
* Run page: https://fevm-serverless-stable-my49a8.cloud.databricks.com/?o=7474652570256692#job/982865610976081/run/121437029937396

| task | result | duration (s) | start (UTC) |
|---|---|---|---|
| semantic_layer_business_case | UPSTREAM_CANCELED | 1794269113 | - |
| publish_to_lakebase | UPSTREAM_CANCELED | 1794269113 | - |
| uc_governance_setup | SUCCESS | 26 | 2026-11-09 23:27:14 UTC |
| land_raw_files | SUCCESS | 115 | 2026-11-09 23:27:41 UTC |
| lakeflow_medallion_pipeline | SUCCESS | 103 | 2026-11-09 23:29:36 UTC |
| train_scam_model | SUCCESS | 129 | 2026-11-09 23:31:19 UTC |
| uc_tags_lineage_audit | SUCCESS | 47 | 2026-11-09 23:31:19 UTC |
| deploy_model_serving | SUCCESS | 584 | 2026-11-09 23:33:29 UTC |
| score_and_genai_enrich | CANCELED | 2026 | 2026-11-09 23:33:29 UTC |
| train_scam_model | SUCCESS | 139 | 2026-11-10 00:07:45 UTC |
| deploy_model_serving | SUCCESS | 644 | 2026-11-10 00:10:05 UTC |
| score_and_genai_enrich | SUCCESS | 242 | 2026-11-10 00:10:05 UTC |
| publish_to_lakebase | FAILED | 130 | 2026-11-10 00:14:07 UTC |
| semantic_layer_business_case | SUCCESS | 15 | 2026-11-10 00:14:07 UTC |
| publish_to_lakebase | SUCCESS | 53 | 2026-11-10 00:16:21 UTC |
