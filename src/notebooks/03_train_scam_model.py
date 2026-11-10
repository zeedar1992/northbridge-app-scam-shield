# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Train the APP-scam risk model (MLflow → Unity Catalog)
# MAGIC
# MAGIC **Business framing.** Northbridge's fraud operations team can work a fixed number of payment holds per day
# MAGIC (the "alert budget"). Today that budget is consumed by a 3-condition rules engine. The question the model must
# MAGIC answer is: **with the same number of alerts, how much more scam *value* do we intercept?** – because under the PSR
# MAGIC reimbursement requirement every scam pound that gets through is (50%) Northbridge's cost.
# MAGIC
# MAGIC * Time-based split (no leakage): **train** 11 Aug – 9 Oct · **test** 10 Oct – 29 Oct · last 10 days = "live" (labels immature).
# MAGIC * LightGBM, positives weighted by value (we care about £, not counts).
# MAGIC * Registered as a **pyfunc** that returns `risk_score`, `risk_band` and human-readable **reason codes**
# MAGIC   (from LightGBM SHAP-style contributions) so the same artefact serves batch scoring, the real-time
# MAGIC   serving endpoint, and the GenAI explanation step.

# COMMAND ----------

# MAGIC %pip install -q lightgbm==4.6.0 mlflow==3.4.0
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("fraud_schema", "northbridge_fraud")
dbutils.widgets.text("ml_schema", "northbridge_ml")
CATALOG, FRAUD, ML = (dbutils.widgets.get(k) for k in ["catalog", "fraud_schema", "ml_schema"])
MODEL_NAME = f"{CATALOG}.{ML}.app_scam_risk_model"
TRAIN_END, TEST_START, TEST_END = "2026-10-09", "2026-10-10", "2026-10-29"

import json, os, tempfile
import numpy as np, pandas as pd, lightgbm as lgb, mlflow
from sklearn.metrics import roc_auc_score, average_precision_score
mlflow.set_registry_uri("databricks-uc")
me = spark.sql("SELECT current_user()").first()[0]
mlflow.set_experiment(f"/Users/{me}/northbridge-app-scam-risk")
print(lgb.__version__, mlflow.__version__, MODEL_NAME)

# COMMAND ----------

NUMERIC = ["amount_gbp", "hour_of_day", "minutes_since_payee_added", "prior_payments_to_payee", "payee_account_age_days",
           "device_age_days", "session_duration_sec", "login_to_payment_sec", "cust_payments_24h", "cust_new_payee_payments_24h",
           "cust_value_24h", "cust_avg_amount_90d", "cust_payments_90d", "amount_to_cust_avg_ratio", "amount_to_cust_max_ratio",
           "payee_distinct_senders_7d", "payee_inbound_payments_7d", "age_years", "tenure_months"]
BOOLEAN = ["is_night", "is_new_payee", "is_new_device", "on_active_call", "reference_risk_keyword", "vulnerability_flag",
           "digital_active", "payee_intel_available"]
CATEGORICAL = ["cop_result", "channel", "payee_bank_type", "payee_category", "payment_type"]
FEATURES = NUMERIC + BOOLEAN + CATEGORICAL

from pyspark.sql import functions as F
df = (spark.table(f"{CATALOG}.{FRAUD}.gold_payment_features")
      .select("payment_id", "event_date", "is_app_scam", "scam_type", "rules_alert",
              *[F.col(c).cast("double").alias(c) for c in NUMERIC], *BOOLEAN, *CATEGORICAL).toPandas())
df["event_date"] = pd.to_datetime(df.event_date)
CATEGORIES = {c: sorted(df[c].dropna().astype(str).unique().tolist()) for c in CATEGORICAL}

def prep(frame: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=frame.index)
    for c in NUMERIC:
        X[c] = pd.to_numeric(frame.get(c), errors="coerce").astype("float64")
    for c in BOOLEAN:
        X[c] = frame.get(c).map(lambda v: np.nan if v is None or (isinstance(v, float) and np.isnan(v)) else float(bool(v))).astype("float64")
    for c in CATEGORICAL:
        X[c] = pd.Categorical(frame.get(c).astype("object").where(frame.get(c).notna(), None), categories=CATEGORIES[c])
    return X[FEATURES]

train = df[df.event_date <= TRAIN_END]; test = df[(df.event_date >= TEST_START) & (df.event_date <= TEST_END)]
print(f"train rows {len(train):,} (scams {int(train.is_app_scam.sum()):,}) | test rows {len(test):,} (scams {int(test.is_app_scam.sum()):,})")

# COMMAND ----------

# value-weighted positives: a £20k impersonation scam matters more than a £150 ticket scam
w_train = np.where(train.is_app_scam == 1, 1.0 + np.sqrt(train.amount_gbp / 1000.0), 1.0)
fit_mask = train.event_date <= "2026-09-29"           # last 10 train days = early-stopping validation
params = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_data_in_leaf=40, feature_fraction=0.85,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, scale_pos_weight=20.0, verbose=-1, seed=7)
dtr = lgb.Dataset(prep(train[fit_mask]), train[fit_mask].is_app_scam, weight=w_train[fit_mask.values])
dva = lgb.Dataset(prep(train[~fit_mask]), train[~fit_mask].is_app_scam, weight=w_train[~fit_mask.values], reference=dtr)
booster = lgb.train(params, dtr, num_boost_round=1500, valid_sets=[dva], callbacks=[lgb.early_stopping(100), lgb.log_evaluation(100)])
print("best iteration", booster.best_iteration)

# COMMAND ----------

# MAGIC %md ## Evaluate against the legacy rules engine at the SAME alert budget

# COMMAND ----------

test = test.copy()
test["score"] = booster.predict(prep(test), num_iteration=booster.best_iteration)
y = test.is_app_scam.values; amt = test.amount_gbp.values
roc, pr = roc_auc_score(y, test.score), average_precision_score(y, test.score)

def catch(mask):
    tp = (mask & (y == 1))
    return dict(alerts=int(mask.sum()), scams_caught=int(tp.sum()), scam_value_caught_gbp=round(float(amt[tp].sum()), 2),
                precision=round(float(tp.sum() / max(mask.sum(), 1)), 4),
                count_recall=round(float(tp.sum() / max(y.sum(), 1)), 4),
                value_recall=round(float(amt[tp].sum() / max(amt[y == 1].sum(), 1)), 4))

rules_mask = test.rules_alert.values.astype(bool)
K = int(rules_mask.sum())
threshold = float(np.sort(test.score.values)[::-1][K - 1])          # model operating point = same alert volume as rules
model_mask = test.score.values >= threshold
rules_res, model_res = catch(rules_mask), catch(model_mask)

# Alternative operating point: how few alerts does the model need to match the rules' caught value?
order = np.argsort(-test.score.values); cum_val = np.cumsum(np.where(y[order] == 1, amt[order], 0.0))
k_match = int(np.searchsorted(cum_val, rules_res["scam_value_caught_gbp"]) + 1)
# High-precision "CRITICAL" band: top 10% of alert budget
crit_threshold = float(np.sort(test.score.values)[::-1][max(K // 10, 1) - 1])

summary = {
    "test_window": f"{TEST_START}..{TEST_END}", "test_payments": int(len(test)), "test_scam_payments": int(y.sum()),
    "test_scam_value_gbp": round(float(amt[y == 1].sum()), 2), "roc_auc": round(roc, 4), "pr_auc": round(pr, 4),
    "alert_budget_K": K, "rules": rules_res, "model_same_budget": model_res,
    "model_alerts_needed_to_match_rules_value": k_match,
    "alert_reduction_at_equal_value_pct": round(100 * (1 - k_match / K), 1),
    "value_uplift_same_budget_pct_points": round(100 * (model_res["value_recall"] - rules_res["value_recall"]), 1),
    "alert_threshold": round(threshold, 6), "critical_threshold": round(crit_threshold, 6),
}
print(json.dumps(summary, indent=2))

# COMMAND ----------

by_type = (test.assign(rules=rules_mask, model=model_mask).query("is_app_scam == 1").groupby("scam_type")
           .apply(lambda g: pd.Series({"scam_payments": len(g), "scam_value_gbp": round(g.amount_gbp.sum(), 0),
                                       "rules_value_recall": round(g.loc[g.rules, "amount_gbp"].sum() / g.amount_gbp.sum(), 3),
                                       "model_value_recall": round(g.loc[g.model, "amount_gbp"].sum() / g.amount_gbp.sum(), 3)})).reset_index())
display(by_type)
imp = pd.DataFrame({"feature": FEATURES, "gain": booster.feature_importance("gain", iteration=booster.best_iteration)}).sort_values("gain", ascending=False)
imp["gain_share"] = (imp.gain / imp.gain.sum()).round(4)
display(imp.head(15))

# COMMAND ----------

# MAGIC %md ## Package as a pyfunc with reason codes and register to Unity Catalog

# COMMAND ----------

REASON_TEXT = {
    "payee_distinct_senders_7d": "Receiving account paid by several unrelated customers this week (mule pattern)",
    "payee_account_age_days": "Receiving account opened very recently",
    "is_new_payee": "Payee added within the last 24 hours",
    "minutes_since_payee_added": "Payment made minutes after the payee was created",
    "prior_payments_to_payee": "No payment history with this payee",
    "on_active_call": "Customer on an active phone call during the session (possible coaching)",
    "cop_result": "Confirmation of Payee did not match the payee name",
    "amount_to_cust_avg_ratio": "Amount far above this customer's normal payments",
    "amount_to_cust_max_ratio": "Largest payment this customer has made in 90 days",
    "amount_gbp": "High payment value",
    "reference_risk_keyword": "Payment reference matches a known scam script",
    "session_duration_sec": "Unusually long, hesitant banking session",
    "login_to_payment_sec": "Long delay between login and payment",
    "payee_bank_type": "Receiving PSP type over-represented in mule activity",
    "cust_new_payee_payments_24h": "Several new-payee payments in the last 24 hours",
    "cust_value_24h": "High outbound value in the last 24 hours",
    "vulnerability_flag": "Customer flagged as potentially vulnerable",
    "age_years": "Customer age profile targeted by this scam type",
    "payee_inbound_payments_7d": "High inbound payment velocity on receiving account",
    "hour_of_day": "Unusual time of day", "is_night": "Night-time payment", "is_new_device": "New device",
    "device_age_days": "Recently registered device", "channel": "Channel risk", "cust_payments_24h": "High payment velocity",
    "payment_type": "Single immediate payment (not a standing order)", "payee_category": "Payee type (personal vs business account)",
    "digital_active": "Customer digital-banking profile", "tenure_months": "Relationship tenure", "payee_intel_available": "No inter-bank intelligence on the receiving account",
    "cust_avg_amount_90d": "Customer's typical payment size", "cust_payments_90d": "Customer payment history depth",
}

class ScamRiskModel(mlflow.pyfunc.PythonModel):
    """Returns risk_score, risk_band and top-3 reason codes for each payment."""
    def load_context(self, context):
        import lightgbm as lgb, json
        self.booster = lgb.Booster(model_file=context.artifacts["booster"])
        self.meta = json.load(open(context.artifacts["meta"]))

    def _prep(self, frame):
        import numpy as np, pandas as pd
        m = self.meta; X = pd.DataFrame(index=frame.index)
        for c in m["numeric"]:
            X[c] = pd.to_numeric(frame[c], errors="coerce").astype("float64") if c in frame else np.nan
        for c in m["boolean"]:
            X[c] = (frame[c].map(lambda v: np.nan if v is None or (isinstance(v, float) and np.isnan(v)) else float(bool(v))).astype("float64")
                    if c in frame else np.nan)
        for c in m["categorical"]:
            s = frame[c].astype("object") if c in frame else pd.Series([None] * len(frame), index=frame.index)
            X[c] = pd.Categorical(s.where(s.notna(), None), categories=m["categories"][c])
        return X[m["features"]]

    def predict(self, context, model_input, params=None):
        import numpy as np, pandas as pd, json
        m = self.meta
        X = self._prep(model_input)
        score = self.booster.predict(X)
        feats = np.array(m["features"])
        floor = m["alert_threshold"] / 4      # TreeSHAP is expensive: only explain payments that are at least MEDIUM risk
        idx = np.where(score >= floor)[0]
        reasons = ["[]"] * len(score)
        if len(idx):
            contrib = self.booster.predict(X.iloc[idx], pred_contrib=True)[:, :-1]
            top = np.argsort(-contrib, axis=1)[:, :3]
            for k, i in enumerate(idx):
                reasons[i] = json.dumps([m["reason_text"].get(feats[j], feats[j]) for j in top[k] if contrib[k, j] > 0])
        band = np.where(score >= m["critical_threshold"], "CRITICAL", np.where(score >= m["alert_threshold"], "HIGH",
                        np.where(score >= m["alert_threshold"] / 4, "MEDIUM", "LOW")))
        return pd.DataFrame({"risk_score": np.round(score, 6), "risk_band": band, "reason_codes": reasons})

meta = {"features": FEATURES, "numeric": NUMERIC, "boolean": BOOLEAN, "categorical": CATEGORICAL, "categories": CATEGORIES,
        "alert_threshold": threshold, "critical_threshold": crit_threshold, "reason_text": REASON_TEXT,
        "best_iteration": booster.best_iteration}
tmp = tempfile.mkdtemp()
booster.save_model(f"{tmp}/booster.txt", num_iteration=booster.best_iteration)
json.dump(meta, open(f"{tmp}/meta.json", "w"))

from mlflow.models import ModelSignature
from mlflow.types.schema import Schema, ColSpec
# explicit contract: numeric + boolean features as double (booleans 0/1), categoricals as string; all optional (nullable)
signature = ModelSignature(
    inputs=Schema([ColSpec("double", c, required=False) for c in NUMERIC + BOOLEAN] + [ColSpec("string", c, required=False) for c in CATEGORICAL]),
    outputs=Schema([ColSpec("double", "risk_score"), ColSpec("string", "risk_band"), ColSpec("string", "reason_codes")]))
example = prep(test.head(5)).copy()
for c in CATEGORICAL: example[c] = example[c].astype("object")
pyfunc = ScamRiskModel(); ctx = type("C", (), {"artifacts": {"booster": f"{tmp}/booster.txt", "meta": f"{tmp}/meta.json"}})()
pyfunc.load_context(ctx)
example_out = pyfunc.predict(None, example)
display(example_out)

with mlflow.start_run(run_name="lgbm_value_weighted") as run:
    mlflow.log_params({**params, "best_iteration": booster.best_iteration, "train_end": TRAIN_END, "test_window": f"{TEST_START}..{TEST_END}",
                       "positive_weighting": "1 + sqrt(amount/1000)", "n_features": len(FEATURES)})
    mlflow.log_metrics({"roc_auc": roc, "pr_auc": pr, "rules_value_recall": rules_res["value_recall"], "model_value_recall": model_res["value_recall"],
                        "rules_precision": rules_res["precision"], "model_precision": model_res["precision"],
                        "alert_reduction_at_equal_value_pct": summary["alert_reduction_at_equal_value_pct"]})
    mlflow.log_dict(summary, "evaluation_summary.json"); mlflow.log_table(imp, "feature_importance.json"); mlflow.log_table(by_type, "recall_by_scam_type.json")
    info = mlflow.pyfunc.log_model(
        name="model", python_model=pyfunc,
        artifacts={"booster": f"{tmp}/booster.txt", "meta": f"{tmp}/meta.json"},
        input_example=example, signature=signature, pip_requirements=["lightgbm==4.6.0", "pandas", "numpy", "mlflow==3.4.0"],
        registered_model_name=MODEL_NAME)
    run_id = run.info.run_id

from mlflow import MlflowClient
client = MlflowClient()
version = info.registered_model_version
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_registered_model(MODEL_NAME, description="Northbridge APP-scam risk model (LightGBM, value-weighted). Outputs risk_score, risk_band, reason_codes. Owner: Fraud Strategy. Alias 'champion' = production.")
client.update_model_version(MODEL_NAME, version, description=f"PR-AUC {pr:.3f}; same-budget value recall {model_res['value_recall']:.1%} vs rules {rules_res['value_recall']:.1%}")
print(f"registered {MODEL_NAME} v{version} @champion  run_id={run_id}")

# COMMAND ----------

rows = [("rules_engine", rules_res), ("ml_model_same_budget", model_res)]
eval_df = spark.createDataFrame(pd.DataFrame([{"approach": a, **r, "model_version": int(version), "test_window": summary["test_window"],
                                               "roc_auc": roc if a != "rules_engine" else None, "pr_auc": pr if a != "rules_engine" else None} for a, r in rows]))
eval_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{ML}.model_evaluation")
spark.createDataFrame(by_type).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{ML}.model_recall_by_scam_type")
spark.sql(f"COMMENT ON TABLE {CATALOG}.{ML}.model_evaluation IS 'Hold-out comparison of the legacy rules engine vs the ML model at the same alert budget (test window {summary['test_window']}).'")
display(spark.table(f"{CATALOG}.{ML}.model_evaluation"))
dbutils.notebook.exit(json.dumps({**summary, "model_version": int(version), "run_id": run_id}))
