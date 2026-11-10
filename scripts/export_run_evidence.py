#!/usr/bin/env python3
"""Export a Lakeflow Job run as TEXT evidence.

For every notebook task of the run it writes, from the EXECUTED notebook (code + real outputs):
  * notebooks_executed/<NN>_<task_key>.ipynb : Jupyter notebook with outputs embedded (GitHub renders cell outputs)
  * evidence/job_run/<task_key>.md           : the same cells + outputs as Markdown
  * the notebook's logged exit value (dbutils.notebook.exit) appended to both
plus evidence/job_run/run_summary.md (task states, durations, attempts) and evidence/job_run/run_log.json (raw run JSON).

Usage: python3 scripts/export_run_evidence.py <job_run_id> [--profile P] [--out evidence/job_run] [--nb-out notebooks_executed]
"""
import argparse
import base64
import json
import pathlib
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone

ANSI = re.compile(r"\x1b\[[0-9;]*m")
ORDER = ["uc_governance_setup", "land_raw_files", "lakeflow_medallion_pipeline", "uc_tags_lineage_audit", "train_scam_model",
         "deploy_model_serving", "score_and_genai_enrich", "publish_to_lakebase", "semantic_layer_business_case"]


def cli(args, profile):
    out = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout, strict=False)


def notebook_model(html: str) -> dict:
    m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html)
    return json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()), strict=False)


def table_text(it: dict, max_rows: int = 40) -> tuple[str, str]:
    """Return (markdown table, html table) for a display() result."""
    cols = [c["name"] for c in it.get("schema", [])]
    rows = it.get("data", [])
    f = lambda v: str(v).replace("|", "\\|").replace("\n", " ")[:220]  # noqa: E731
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(f(v) for v in r) + " |" for r in rows[:max_rows]]
    if len(rows) > max_rows:
        md.append(f"\n_… {len(rows) - max_rows} more rows truncated_")
    esc = lambda v: str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    html = ("<table><thead><tr>" + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in r) + "</tr>" for r in rows[:max_rows]) + "</tbody></table>")
    return "\n".join(md), html


def outputs_of(r: dict | None):
    """Yield ('table', md, html) | ('text', str) | ('error', str) for a command's results."""
    if not r:
        return
    items = r.get("data") if r.get("type") == "listResults" else [r]
    for it in items or []:
        t = it.get("type")
        if t == "table" and it.get("schema"):
            md, html = table_text(it)
            yield ("table", md, html)
        elif t in ("ansi", "text"):
            txt = ANSI.sub("", str(it.get("data", "")))
            txt = "\n".join(ln for ln in txt.splitlines() if "Effective usage policy" not in ln).rstrip()   # drop Spark Connect session-policy noise
            if txt:
                yield ("text", txt[:15000])
        elif t == "html":
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(it.get("data", "")))).strip()
            if txt:
                yield ("text", txt[:4000])
        elif t == "error":
            yield ("error", ANSI.sub("", str(it.get("data", "")))[:4000])
    if r.get("type") == "error" or r.get("errorSummary"):
        yield ("error", ANSI.sub("", str(r.get("errorSummary") or r.get("data")))[:4000])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--profile", default="fevm-serverless-stable-my49a8")
    ap.add_argument("--out", default="evidence/job_run")
    ap.add_argument("--nb-out", default="notebooks_executed")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    nbo = pathlib.Path(a.nb_out); nbo.mkdir(parents=True, exist_ok=True)
    run = cli(["jobs", "get-run", a.run_id], a.profile)
    (out / "run_log.json").write_text(json.dumps({k: run.get(k) for k in ["run_id", "run_name", "state", "start_time", "end_time", "run_page_url",
                                                                           "job_parameters", "repair_history"]} |
                                                 {"tasks": [{k: t.get(k) for k in ["task_key", "run_id", "attempt_number", "state", "start_time",
                                                                                   "end_time", "execution_duration", "notebook_task", "pipeline_task"]}
                                                            for t in run["tasks"]]}, indent=2, default=str))
    ts = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ms else "-"  # noqa: E731
    summary = [f"# Job run {a.run_id}: {run.get('run_name')}", "",
               f"* Result: **{run['state'].get('result_state')}**  ·  start {ts(run.get('start_time'))}  ·  end {ts(run.get('end_time'))}",
               f"* Job parameters: `{json.dumps({p['name']: p.get('value', p.get('default')) for p in run.get('job_parameters', [])})}`",
               f"* Run page: {run.get('run_page_url')}", "", "| task | task run id | result | duration (s) | start (UTC) |", "|---|---|---|---|---|"]
    tasks = sorted(run["tasks"], key=lambda t: t.get("start_time", 0))
    latest = {}
    for t in tasks:
        dur = round((t.get("end_time", 0) - t.get("start_time", 0)) / 1000) if t.get("end_time") else "-"
        summary.append(f"| {t['task_key']} | {t['run_id']} | {t['state'].get('result_state', t['state'].get('life_cycle_state'))} | {dur} | {ts(t.get('start_time'))} |")
        if t["state"].get("result_state") == "SUCCESS":
            latest[t["task_key"]] = t
    summary += ["", "Rows with the same task key are attempts. A later SUCCESS is a repair after a fix; see `docs/ai-assisted-build.md`.", ""]
    for key, t in sorted(latest.items(), key=lambda kv: ORDER.index(kv[0]) if kv[0] in ORDER else 99):
        if "notebook_task" not in t:
            continue
        nb_name = pathlib.Path(t["notebook_task"]["notebook_path"]).name
        exp = cli(["jobs", "export-run", str(t["run_id"]), "--views-to-export", "CODE"], a.profile)
        model = notebook_model(exp["views"][0]["content"])
        try:
            exit_val = cli(["jobs", "get-run-output", str(t["run_id"])], a.profile).get("notebook_output", {}).get("result")
        except Exception:  # noqa: BLE001
            exit_val = None
        header = (f"Executed by Lakeflow Job run {a.run_id} · task `{key}` · task run {t['run_id']} · result {t['state'].get('result_state')} · "
                  f"{ts(t.get('start_time'))} → {ts(t.get('end_time'))} · source `src/notebooks/{nb_name}.py`")
        md = [f"# Task `{key}` · notebook `{nb_name}` (executed, with outputs)", "", header, "",
              "> Exported from the executed job run by `scripts/export_run_evidence.py`. Every output below is real.", ""]
        cells = [{"cell_type": "markdown", "metadata": {}, "source": [f"**{header}**\n\n_Executed notebook exported from the job run; outputs are real._"]}]
        n_out = 0
        for c in sorted(model["commands"], key=lambda c: c.get("position", 0)):
            src = c.get("command", "")
            if src.lstrip().startswith("%md"):
                body = re.sub(r"^%md\s?", "", src.lstrip()).strip()
                md += [body, ""]
                cells.append({"cell_type": "markdown", "metadata": {}, "source": [body]})
                continue
            outs, nb_outs = [], []
            for o in outputs_of(c.get("results")):
                n_out += 1
                if o[0] == "table":
                    outs.append(o[1])
                    nb_outs.append({"output_type": "display_data", "metadata": {}, "data": {"text/html": [o[2]], "text/plain": [o[1]]}})
                elif o[0] == "text":
                    outs.append("```text\n" + o[1] + "\n```")
                    nb_outs.append({"output_type": "stream", "name": "stdout", "text": [o[1] + "\n"]})
                else:
                    outs.append("```text\nERROR: " + o[1] + "\n```")
                    nb_outs.append({"output_type": "stream", "name": "stderr", "text": [o[1] + "\n"]})
            md.append("```python\n" + src.strip() + "\n```")
            if outs:
                md.append("**Output:**\n\n" + "\n\n".join(outs))
            md.append("")
            cells.append({"cell_type": "code", "metadata": {}, "execution_count": len(cells), "source": [src.strip()], "outputs": nb_outs})
        if exit_val:
            pretty = exit_val
            try:
                pretty = json.dumps(json.loads(exit_val), indent=2)
            except Exception:  # noqa: BLE001
                pass
            md += ["## Logged notebook exit value (`dbutils.notebook.exit`, from the Jobs API)", "", "```json", pretty, "```"]
            cells.append({"cell_type": "markdown", "metadata": {}, "source": ["**Logged notebook exit value (Jobs API `get-run-output`):**\n\n```json\n" + pretty + "\n```"]})
        (out / f"{key}.md").write_text("\n".join(md))
        idx = ORDER.index(key) if key in ORDER else 99
        for i, cell in enumerate(cells):
            cell["id"] = f"{key[:20]}-{i:03d}"
        nb = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
              "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                           "language_info": {"name": "python"}, "databricks_job_run": {"job_run_id": a.run_id, "task_run_id": t["run_id"], "task_key": key}}}
        (nbo / f"{idx:02d}_{key}.ipynb").write_text(json.dumps(nb, indent=1))
        print(f"wrote {key}: {n_out} outputs, exit value {'yes' if exit_val else 'no'}")
    (out / "run_summary.md").write_text("\n".join(summary) + "\n")
    print("wrote", out / "run_summary.md")


if __name__ == "__main__":
    main()
