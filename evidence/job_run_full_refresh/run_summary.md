# Job run 121437029937396: northbridge-app-scam-shield-journey

* Result: **SUCCESS**  ·  start 2026-11-09 23:27:14 UTC  ·  end 2026-11-10 00:20:49 UTC
* Job parameters: `{"catalog": "serverless_stable_my49a8_catalog", "through_date": "2026-11-07"}`
* Run page: https://fevm-serverless-stable-my49a8.cloud.databricks.com/?o=7474652570256692#job/982865610976081/run/121437029937396

| task | task run id | result | duration (s) | start (UTC) |
|---|---|---|---|---|
| semantic_layer_business_case | 1049005871420152 | UPSTREAM_CANCELED | 1794269113 | - |
| publish_to_lakebase | 228984558861893 | UPSTREAM_CANCELED | 1794269113 | - |
| uc_governance_setup | 899109565423382 | SUCCESS | 26 | 2026-11-09 23:27:14 UTC |
| land_raw_files | 984526092306530 | SUCCESS | 115 | 2026-11-09 23:27:41 UTC |
| lakeflow_medallion_pipeline | 562634612166931 | SUCCESS | 103 | 2026-11-09 23:29:36 UTC |
| train_scam_model | 682058945068113 | SUCCESS | 129 | 2026-11-09 23:31:19 UTC |
| uc_tags_lineage_audit | 227463159695093 | SUCCESS | 47 | 2026-11-09 23:31:19 UTC |
| deploy_model_serving | 767390085858746 | SUCCESS | 584 | 2026-11-09 23:33:29 UTC |
| score_and_genai_enrich | 837237751829170 | CANCELED | 2026 | 2026-11-09 23:33:29 UTC |
| train_scam_model | 1050825763401354 | SUCCESS | 139 | 2026-11-10 00:07:45 UTC |
| deploy_model_serving | 772303946353091 | SUCCESS | 644 | 2026-11-10 00:10:05 UTC |
| score_and_genai_enrich | 501525153117017 | SUCCESS | 242 | 2026-11-10 00:10:05 UTC |
| publish_to_lakebase | 275983756164005 | FAILED | 130 | 2026-11-10 00:14:07 UTC |
| semantic_layer_business_case | 137984998434180 | SUCCESS | 15 | 2026-11-10 00:14:07 UTC |
| publish_to_lakebase | 399409351716231 | SUCCESS | 53 | 2026-11-10 00:16:21 UTC |

Rows with the same task key are attempts. A later SUCCESS is a repair after a fix; see `docs/ai-assisted-build.md`.

