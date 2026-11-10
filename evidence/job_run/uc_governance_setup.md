# Task `uc_governance_setup` · notebook `00_governance_setup` (executed, with outputs)

Executed by Lakeflow Job run 886593886805341 · task `uc_governance_setup` · task run 291118273447486 · result SUCCESS · 2026-11-10 09:02:09 UTC → 2026-11-10 09:02:38 UTC · source `src/notebooks/00_governance_setup.py`

> Exported from the executed job run by `scripts/export_run_evidence.py`. Every output below is real.

# 00 · Unity Catalog governance setup (runs BEFORE the pipeline)

Creates the governance primitives the Lakeflow pipeline binds to:
* **Column-mask functions** – PII is only visible to the account group `northbridge-pii-readers`
  (managed in the bank's IdP via SCIM). Everyone else – fraud analysts, data scientists, the Genie Agent,
  the app's service principal – sees masked values. ML features are derived from PII *inside* the governed
  pipeline (age band, postcode district) so downstream consumers never need raw identifiers.
* Landing-zone folders in the UC Volume.

Schemas, the volume and schema-level grants are declared in the bundle (`resources/unity_catalog.yml`).

```python
dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("fraud_schema", "northbridge_fraud")
dbutils.widgets.text("raw_schema", "northbridge_raw")
CATALOG, FRAUD, RAW = (dbutils.widgets.get(k) for k in ["catalog", "fraud_schema", "raw_schema"])
PII_GROUP = "northbridge-pii-readers"
```

```python
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
```
**Output:**

| masked_name | masked_sort_code | masked_dob | current_user_is_pii_reader | evaluated_as |
|---|---|---|---|---|
| M***************n | 3******2 | 1948-01-01 | False | zeeshan.dar@databricks.com |

```python
import os
landing = f"/Volumes/{CATALOG}/{RAW}/landing"
for sub in ["customers", "accounts", "payees", "payments", "scam_claims"]:
    os.makedirs(f"{landing}/{sub}", exist_ok=True)
print(sorted(os.listdir(landing)))
```
**Output:**

```text
['accounts', 'customers', 'payees', 'payments', 'scam_claims']
```

```python
display(spark.sql(f"""
SELECT routine_schema, routine_name, comment
FROM {CATALOG}.information_schema.routines
WHERE routine_schema = '{FRAUD}' ORDER BY routine_name
"""))
```
**Output:**

| routine_schema | routine_name | comment |
|---|---|---|
| northbridge_fraud | mask_pii_date | Column mask: full date of birth only for northbridge-pii-readers; otherwise truncated to 1 January of the birth year. |
| northbridge_fraud | mask_pii_string | Column mask: clear text only for members of account group northbridge-pii-readers; otherwise first + last character with asterisks. |
