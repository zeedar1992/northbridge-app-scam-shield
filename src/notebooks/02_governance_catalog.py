# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Unity Catalog governance – tags, ownership metadata, masks proof, lineage
# MAGIC
# MAGIC Runs after the Lakeflow pipeline has published bronze/silver/gold. It:
# MAGIC 1. Applies **governed tags** (workspace tag policies: `data_classification`, `class.*` PII classes, `system.certification_status`) plus project tags at table and column level.
# MAGIC 2. **Proves the column masks work** – queries `silver_customers` as the job identity (not a PII reader).
# MAGIC 3. Prints the **automatically captured lineage** (system.access.table_lineage) for the gold feature table.
# MAGIC 4. Lists effective grants so an auditor can see who can read what.

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("fraud_schema", "northbridge_fraud")
CATALOG, FRAUD = dbutils.widgets.get("catalog"), dbutils.widgets.get("fraud_schema")
fq = lambda t: f"{CATALOG}.{FRAUD}.{t}"

# COMMAND ----------

# Governed tag keys defined by the workspace tag policies are reused (data_classification, class.*, system.certification_status);
# project-specific keys are prefixed nb_.
TABLE_TAGS = {
    "bronze_customers":      {"data_classification": "pii", "nb_access_tier": "restricted", "nb_regulation": "UK_GDPR"},
    "bronze_accounts":       {"data_classification": "pii", "nb_access_tier": "restricted", "nb_regulation": "UK_GDPR"},
    "bronze_payments":       {"nb_access_tier": "confidential", "nb_regulation": "PSR_APP_REIMBURSEMENT"},
    "bronze_payees":         {"nb_access_tier": "confidential"},
    "bronze_scam_claims":    {"nb_access_tier": "confidential", "nb_regulation": "PSR_APP_REIMBURSEMENT"},
    "silver_customers":      {"data_classification": "pii", "nb_access_tier": "confidential", "nb_pii_protection": "column_masked", "nb_regulation": "UK_GDPR"},
    "silver_accounts":       {"data_classification": "pii", "nb_access_tier": "confidential", "nb_pii_protection": "column_masked"},
    "silver_payments":       {"nb_access_tier": "confidential", "nb_regulation": "PSR_APP_REIMBURSEMENT"},
    "silver_scam_claims":    {"nb_access_tier": "confidential", "nb_regulation": "PSR_APP_REIMBURSEMENT"},
    "gold_payment_features": {"nb_access_tier": "internal", "nb_pii_protection": "no_direct_identifiers", "nb_ml_use": "training_and_scoring"},
    "gold_daily_fraud_kpis": {"nb_access_tier": "internal", "system.certification_status": "certified"},
    "gold_mule_watchlist":   {"nb_access_tier": "confidential", "nb_sharing": "interbank_data_sharing"},
}
PII_CLASS = {"full_name": "class.name", "date_of_birth": "class.date_of_birth", "email": "class.email_address",
             "mobile_phone": "class.phone_number", "postcode": "class.location", "sort_code": "class.bank_number", "account_number": "class.bank_number"}
COLUMN_TAGS = {
    "silver_customers": ["full_name", "date_of_birth", "email", "mobile_phone", "postcode"],
    "bronze_customers": ["full_name", "date_of_birth", "email", "mobile_phone", "postcode"],
    "silver_accounts":  ["sort_code", "account_number"],
    "bronze_accounts":  ["sort_code", "account_number"],
}
for t, tags in TABLE_TAGS.items():
    kv = ", ".join(f"'{k}' = '{v}'" for k, v in tags.items())
    spark.sql(f"ALTER TABLE {fq(t)} SET TAGS ({kv})")
for t, cols in COLUMN_TAGS.items():
    for c in cols:
        spark.sql(f"ALTER TABLE {fq(t)} ALTER COLUMN {c} SET TAGS ('{PII_CLASS[c]}')")
print("tags applied")

# COMMAND ----------

# MAGIC %md ### Tags as recorded in Unity Catalog

# COMMAND ----------

display(spark.sql(f"""
SELECT table_name, collect_list(concat(tag_name, '=', tag_value)) AS tags
FROM {CATALOG}.information_schema.table_tags WHERE schema_name = '{FRAUD}'
GROUP BY table_name ORDER BY table_name"""))
display(spark.sql(f"""
SELECT table_name, column_name, tag_name AS governed_pii_class
FROM {CATALOG}.information_schema.column_tags WHERE schema_name = '{FRAUD}' AND tag_name LIKE 'class.%'
ORDER BY table_name, column_name"""))

# COMMAND ----------

# MAGIC %md ### Column masks bound to silver tables (defined in the pipeline DDL)

# COMMAND ----------

display(spark.sql(f"""
SELECT table_name, column_name, mask_name
FROM {CATALOG}.information_schema.column_masks WHERE table_schema = '{FRAUD}' ORDER BY table_name, column_name"""))

# COMMAND ----------

# MAGIC %md ### Proof: what a non-PII-reader (this job identity) actually sees

# COMMAND ----------

display(spark.sql(f"""
SELECT current_user() AS evaluated_as, is_account_group_member('northbridge-pii-readers') AS is_pii_reader,
       customer_id, full_name, date_of_birth, email, mobile_phone, postcode, postcode_district, age_band, vulnerability_flag
FROM {fq('silver_customers')} ORDER BY customer_id LIMIT 5"""))
display(spark.sql(f"SELECT account_id, sort_code, account_number, product FROM {fq('silver_accounts')} ORDER BY account_id LIMIT 3"))

# COMMAND ----------

# MAGIC %md ### Lineage captured automatically by Unity Catalog

# COMMAND ----------

display(spark.sql(f"""
SELECT DISTINCT source_table_full_name, target_table_full_name, entity_type
FROM system.access.table_lineage
WHERE target_table_catalog = '{CATALOG}' AND target_table_schema IN ('{FRAUD}', 'northbridge_ml', 'northbridge_ops')
  AND source_table_full_name IS NOT NULL AND event_date >= current_date() - INTERVAL 7 DAYS
ORDER BY target_table_full_name, source_table_full_name"""))

# COMMAND ----------

# MAGIC %md ### Effective grants on the Northbridge schemas

# COMMAND ----------

display(spark.sql(f"""
SELECT grantee, schema_name, privilege_type
FROM {CATALOG}.information_schema.schema_privileges
WHERE schema_name LIKE 'northbridge%' ORDER BY schema_name, grantee, privilege_type"""))
