# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Unity Catalog governance setup (runs BEFORE the pipeline)
# MAGIC
# MAGIC Creates the governance primitives the Lakeflow pipeline binds to:
# MAGIC * **Column-mask functions** – PII is only visible to the account group `northbridge-pii-readers`
# MAGIC   (managed in the bank's IdP via SCIM). Everyone else – fraud analysts, data scientists, the Genie Agent,
# MAGIC   the app's service principal – sees masked values. ML features are derived from PII *inside* the governed
# MAGIC   pipeline (age band, postcode district) so downstream consumers never need raw identifiers.
# MAGIC * Landing-zone folders in the UC Volume.
# MAGIC
# MAGIC Schemas, the volume and schema-level grants are declared in the bundle (`resources/unity_catalog.yml`).

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("fraud_schema", "northbridge_fraud")
dbutils.widgets.text("raw_schema", "northbridge_raw")
CATALOG, FRAUD, RAW = (dbutils.widgets.get(k) for k in ["catalog", "fraud_schema", "raw_schema"])
PII_GROUP = "northbridge-pii-readers"

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{FRAUD}.mask_pii_string(v STRING)
RETURNS STRING
COMMENT 'Column mask: clear text only for members of account group {PII_GROUP}; otherwise first + last character with asterisks.'
RETURN CASE
  WHEN v IS NULL THEN NULL
  WHEN is_account_group_member('{PII_GROUP}') THEN v
  WHEN length(v) <= 2 THEN '**'
  ELSE concat(substr(v, 1, 1), repeat('*', length(v) - 2), substr(v, -1, 1))
END
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{FRAUD}.mask_pii_date(d DATE)
RETURNS DATE
COMMENT 'Column mask: full date of birth only for {PII_GROUP}; otherwise truncated to 1 January of the birth year.'
RETURN CASE WHEN d IS NULL THEN NULL WHEN is_account_group_member('{PII_GROUP}') THEN d ELSE make_date(year(d), 1, 1) END
""")

display(spark.sql(f"""
SELECT {CATALOG}.{FRAUD}.mask_pii_string('Margaret Thompson') AS masked_name,
       {CATALOG}.{FRAUD}.mask_pii_string('30-45-12')          AS masked_sort_code,
       {CATALOG}.{FRAUD}.mask_pii_date(DATE'1948-06-17')      AS masked_dob,
       is_account_group_member('{PII_GROUP}')                 AS current_user_is_pii_reader,
       current_user()                                         AS evaluated_as
"""))

# COMMAND ----------

import os
landing = f"/Volumes/{CATALOG}/{RAW}/landing"
for sub in ["customers", "accounts", "payees", "payments", "scam_claims"]:
    os.makedirs(f"{landing}/{sub}", exist_ok=True)
print(sorted(os.listdir(landing)))

# COMMAND ----------

display(spark.sql(f"""
SELECT routine_schema, routine_name, comment
FROM {CATALOG}.information_schema.routines
WHERE routine_schema = '{FRAUD}' ORDER BY routine_name
"""))
