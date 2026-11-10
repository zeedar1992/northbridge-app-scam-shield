#!/usr/bin/env python3
"""Fill the deck + demo-script templates with MEASURED values from the latest job run and UC tables.

Usage: python3 scripts/render_docs.py <job_run_id> [--profile P] [--warehouse ID]
Writes deck/northbridge-scam-shield-deck.md and docs/demo-script.md, plus evidence/headline_numbers.json.
"""
import argparse
import json
import pathlib
import subprocess

C = "serverless_stable_my49a8_catalog"


def cli(args, profile):
    r = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def q(sql, profile, wh):
    return cli(["experimental", "aitools", "tools", "query", sql, "--warehouse", wh], profile)


def task_exit(run, key, profile):
    t = next(t for t in run["tasks"] if t["task_key"] == key)
    return json.loads(cli(["jobs", "get-run-output", str(t["run_id"])], profile)["notebook_output"]["result"])


gbp = lambda v: f"£{v / 1e6:.1f}m" if abs(v) >= 1e6 else f"£{v:,.0f}"  # noqa: E731
pct = lambda v, d=0: f"{100 * v:.{d}f}%"  # noqa: E731


def _block_after(text, marker, fence="```"):
    """Return the first fenced block that follows `marker` in `text` (verbatim)."""
    i = text.index(marker)
    j = text.index(fence, i)
    k = text.index(fence, j + 3)
    return text[j:k + 3]


def _block_containing(text, needle):
    """Return the fenced block that contains `needle` (verbatim)."""
    i = text.index(needle)
    j = text.rindex("```", 0, i)
    k = text.index("```", i)
    return text[j:k + 3]


def _section_table(text, heading, max_rows=8):
    i = text.index(heading)
    lines = [ln for ln in text[i:].split("\n")[1:] if ln.startswith("|")]
    out = []
    for ln in lines:
        out.append(ln)
        if len(out) >= max_rows + 2:
            break
    return "\n".join(out)


def proof_section(root):
    ev = root / "evidence"
    train = (ev / "job_run/train_scam_model.md").read_text()
    serve = (ev / "job_run/deploy_model_serving.md").read_text()
    lb = (ev / "job_run/publish_to_lakebase.md").read_text()
    pq = (ev / "platform_queries.md").read_text()
    pl = (ev / "pipeline_event_log.md").read_text()
    reg = next(ln for ln in train.splitlines() if ln.startswith("registered "))
    incr_i = pl.index("full_refresh=false · 2026-11-10")
    rows, started = [], False
    for ln in pl[incr_i:].split("\n")[1:60]:
        if ln.startswith("|"):
            rows.append(ln); started = True
        elif started:
            break
    incr = "\n".join(rows[:2] + [ln for ln in rows[2:] if any(f"| {k} |" in ln for k in
                     ("bronze_payments", "bronze_customers", "bronze_payees", "bronze_scam_claims", "silver_payments_validated",
                      "silver_payments_quarantine", "silver_payments_dedupe"))])
    return "\n".join([
        "### 1 · Lakeflow pipeline: incremental update for the next business day (pipeline event log)",
        "Only the new day's file is read; customers/payees untouched; AUTO CDC upserts; bad rows quarantined. Source: [`evidence/pipeline_event_log.md`](evidence/pipeline_event_log.md)", "", incr, "",
        "### 2 · Unity Catalog: what a non-PII reader sees (live query)",
        "Source: [`evidence/platform_queries.md`](evidence/platform_queries.md#7-unity-catalog-what-a-non-pii-reader-sees-masked)", "",
        _section_table(pq, "## 7. Unity Catalog", 3), "",
        "### 3 · ML: hold-out evaluation printed by the training notebook (verbatim cell output)",
        "Source: [`notebooks_executed/04_train_scam_model.ipynb`](notebooks_executed/04_train_scam_model.ipynb)", "",
        _block_containing(train, '"test_window": "2026-10-10..2026-10-29"'), "", "```text\n" + reg + "\n```", "",
        "### 4 · Real-time Model Serving smoke test (logged notebook exit value)",
        "Source: [`notebooks_executed/05_deploy_model_serving.ipynb`](notebooks_executed/05_deploy_model_serving.ipynb)", "",
        _block_after(serve, "## Logged notebook exit value"), "",
        "### 5 · GenAI: case notes written by Claude via `ai_query` (live query of the alert queue)",
        "Source: [`evidence/platform_queries.md`](evidence/platform_queries.md#15-genai-three-verbatim-case-notes)", "",
        _section_table(pq, "## 15. GenAI", 2), "",
        "### 6 · Lakebase: point-lookup latency + Lakehouse Sync back to UC (verbatim notebook output)",
        "Source: [`notebooks_executed/07_publish_to_lakebase.ipynb`](notebooks_executed/07_publish_to_lakebase.ipynb)", "",
        _block_after(lb, "## Logged notebook exit value"), "",
        "\n".join(lb[lb.index("| uc_history_table"):].split("\n")[:5]), "",
        "### 7 · Genie and the deployed app",
        "Genie: 9 answered questions with generated SQL in [`evidence/genie_transcripts.md`](evidence/genie_transcripts.md). "
        "App: 17 real HTTPS calls, all HTTP 200, in [`evidence/app_session.md`](evidence/app_session.md).",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--profile", default="fevm-serverless-stable-my49a8")
    ap.add_argument("--warehouse", default="1035b8c40230fe40")
    a = ap.parse_args()
    run = cli(["jobs", "get-run", a.run_id], a.profile)
    ev = task_exit(run, "train_scam_model", a.profile)
    try:
        lb = task_exit(run, "publish_to_lakebase", a.profile)
    except Exception:  # noqa: BLE001
        lb = {"latency": {"p50_ms_3_queries": "n/a"}}
    bc = {r["metric_key"]: r for r in q(f"SELECT * FROM {C}.northbridge_ml.business_case ORDER BY sort_order", a.profile, a.warehouse)}
    types = q(f"SELECT * FROM {C}.northbridge_ml.model_recall_by_scam_type ORDER BY CAST(scam_value_gbp AS DOUBLE) DESC", a.profile, a.warehouse)
    app = cli(["apps", "get", "northbridge-scam-shield"], a.profile).get("url", "")
    R, M = ev["rules"], ev["model_same_budget"]
    v = lambda k: float(bc[k]["value"])  # noqa: E731
    fp = lambda p: f"{(1 - p) / p:.1f}"  # noqa: E731
    tok = {
        "NET_VALUE": gbp(v("total_annual_value")), "NET_SAVING": gbp(v("annual_net_saving_gbp")), "NB_LOSSES": gbp(v("nb_losses_today")),
        "ANALYST_HOURS": f"{v('analyst_hours_saved'):,.0f}", "RULES_VR": pct(R["value_recall"]), "MODEL_VR": pct(M["value_recall"]),
        "RULES_CR": pct(R["count_recall"]), "MODEL_CR": pct(M["count_recall"]), "RULES_PREC": pct(R["precision"], 1), "MODEL_PREC": pct(M["precision"], 1),
        "PREC_X": f"{M['precision'] / R['precision']:.1f}", "FP_RULES": fp(R["precision"]), "FP_MODEL": fp(M["precision"]),
        "RULES_ALERTS": f"{R['alerts']:,}", "MODEL_ALERTS": f"{M['alerts']:,}", "VR_UPLIFT": f"{100 * (M['value_recall'] - R['value_recall']):.0f}",
        "K_MATCH": f"{ev['model_alerts_needed_to_match_rules_value']:,}", "ALERT_REDUCTION": f"{ev['alert_reduction_at_equal_value_pct']:.0f}",
        "PR_AUC": f"{ev['pr_auc']:.3f}", "ROC_AUC": f"{ev['roc_auc']:.3f}", "MODEL_VERSION": str(ev["model_version"]),
        "ROI": f"{(v('total_annual_value') - v('platform_run_cost')) / -v('platform_run_cost'):.0f}",
        "PAYBACK": f"{12 * -v('platform_run_cost') / (v('total_annual_value') - v('platform_run_cost')):.1f}",
        "RUN_COST": gbp(-v("platform_run_cost")),
        "PG_P50": str(lb.get("latency", {}).get("p50_ms_3_queries", "n/a")), "APP_URL": app,
    }
    unit = lambda r: gbp(float(r["value"])) if r["unit"] == "GBP" else pct(float(r["value"]), 1) if r["unit"] == "pct" else f"{float(r['value']):,.1f}"  # noqa: E731
    tok["BIZ_TABLE"] = "| Line | Value | Basis |\n|---|---|---|\n" + "\n".join(
        f"| {'**' + r['metric'] + '**' if str(r['is_total']).lower() == 'true' else r['metric']} | {unit(r)} | {r['basis']} |" for r in bc.values())
    tok["TYPE_TABLE"] = "| Scam type | Scam payments | Scam value | Rules value recall | Model value recall |\n|---|---|---|---|---|\n" + "\n".join(
        f"| {t['scam_type']} | {int(float(t['scam_payments']))} | {gbp(float(t['scam_value_gbp']))} | {pct(float(t['rules_value_recall']))} | {pct(float(t['model_value_recall']))} |" for t in types)
    root = pathlib.Path(__file__).resolve().parents[1]
    tok["PROOF"] = proof_section(root)
    for tmpl, out in [("docs/templates/deck.md.tmpl", "deck/northbridge-scam-shield-deck.md"), ("docs/templates/demo-script.md.tmpl", "docs/demo-script.md"),
                      ("docs/templates/README.md.tmpl", "README.md")]:
        s = (root / tmpl).read_text()
        for k, val in tok.items():
            s = s.replace("{{" + k + "}}", val)
        assert "{{" not in s, f"unfilled token in {tmpl}: {s[s.index('{{'):s.index('{{') + 30]}"
        (root / out).parent.mkdir(parents=True, exist_ok=True)
        (root / out).write_text(s)
        print("wrote", out)
    (root / "evidence/headline_numbers.json").write_text(json.dumps({"job_run_id": a.run_id, **{k: tok[k] for k in tok if k not in ("BIZ_TABLE", "TYPE_TABLE")},
                                                                      "evaluation": ev}, indent=2))
    print(json.dumps({k: tok[k] for k in ["NET_VALUE", "RULES_VR", "MODEL_VR", "RULES_PREC", "MODEL_PREC", "ROI", "PAYBACK"]}, indent=2))


if __name__ == "__main__":
    main()
