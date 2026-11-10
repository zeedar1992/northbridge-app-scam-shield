const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const gbp = (v, d = 0) => v == null ? "–" : "£" + Number(v).toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = (v, d = 1) => v == null ? "–" : (Number(v) * 100).toFixed(d) + "%";
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || j.error || r.statusText);
  return j;
}
const parseReasons = (r) => { try { return Array.isArray(r) ? r : JSON.parse(r || "[]"); } catch { return [String(r)]; } };

// ------------------------------------------------------------------ navigation
$$("nav button").forEach((b) => b.addEventListener("click", () => {
  $$("nav button").forEach((x) => x.classList.toggle("active", x === b));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + b.dataset.view));
  loaders[b.dataset.view]?.();
}));

api("/api/health").then((h) => { $("#health").textContent = `Lakebase ${h.lakebase_ms} ms · model ${h.serving_endpoint}`; })
  .catch((e) => { $("#health").textContent = "health: " + e.message; });

// ------------------------------------------------------------------ outcome
let outcomeLoaded = false;
async function loadOutcome() {
  if (outcomeLoaded) return; outcomeLoaded = true;
  const o = await api("/api/outcome");
  const ev = Object.fromEntries(o.evaluation.map((r) => [r.approach, r]));
  const R = ev.rules_engine, M = ev.ml_model_same_budget;
  const bc = Object.fromEntries(o.business_case.map((r) => [r.metric_key, r]));
  const k = [
    ["Scam value intercepted", pct(M.value_recall, 0), `vs ${pct(R.value_recall, 0)} with today's rules, same number of alerts`],
    ["Alert precision", pct(M.precision), `vs ${pct(R.precision)}: fewer genuine customers blocked`],
    ["Annual net loss avoided", gbp(bc.annual_net_saving_gbp?.value), "after the receiving bank's 50% share and an intervention success rate"],
    ["Analyst hours released / yr", Number(bc.analyst_hours_saved?.value || 0).toLocaleString("en-GB"), "from GenAI case notes + fewer false alerts"],
    ["Open alerts (live)", o.live.open_alerts, `${o.live.decisions_total} decisions logged · ${gbp(o.live.protected_gbp_total)} protected`],
  ];
  $("#kpis").innerHTML = k.map(([l, v, d]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${esc(d)}</div></div>`).join("");

  $("#bizcase").innerHTML = "<tr><th>Line</th><th class='num'>Value</th><th>Basis</th></tr>" + o.business_case.map((r) =>
    `<tr class="${r.is_total === "true" || r.is_total === true ? "total" : ""}"><td>${esc(r.metric)}</td><td class="num">${r.unit === "GBP" ? gbp(r.value) : r.unit === "pct" ? pct(r.value) : Number(r.value).toLocaleString("en-GB")}</td><td class="muted">${esc(r.basis)}</td></tr>`).join("");
  $("#liveops").innerHTML = [["Open alerts", o.live.open_alerts], ["Decisions today", o.live.decisions_today],
    ["Scams stopped (logged)", o.live.scams_stopped], ["£ protected (logged)", gbp(o.live.protected_gbp_total)]]
    .map(([l, v]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div></div>`).join("");

  const md = Object.fromEntries(o.model_daily.map((r) => [r.event_date, r]));
  const days = o.daily.filter((r) => r.event_date >= "2026-10-10");
  new Chart($("#chartDaily"), { type: "bar", data: { labels: days.map((r) => r.event_date.slice(5)), datasets: [
    { label: "Confirmed scam value", data: days.map((r) => +r.confirmed_scam_value_gbp), backgroundColor: "#d7dde7" },
    { label: "Caught by rules", data: days.map((r) => +r.scam_value_alerted_by_rules_gbp), backgroundColor: "#8a96ab" },
    { label: "Caught by model", data: days.map((r) => +(md[r.event_date]?.scam_value_alerted_by_model_gbp || 0)), backgroundColor: "#0f8b8d" }] },
    options: { plugins: { legend: { position: "bottom" } }, scales: { y: { ticks: { callback: (v) => "£" + (v / 1000) + "k" } } } } });
  new Chart($("#chartType"), { type: "bar", data: { labels: o.by_type.map((r) => r.scam_type), datasets: [
    { label: "Rules", data: o.by_type.map((r) => +r.rules_value_recall * 100), backgroundColor: "#8a96ab" },
    { label: "Model", data: o.by_type.map((r) => +r.model_value_recall * 100), backgroundColor: "#0f8b8d" }] },
    options: { indexAxis: "y", plugins: { legend: { position: "bottom" } }, scales: { x: { max: 100, ticks: { callback: (v) => v + "%" } } } } });
}

// ------------------------------------------------------------------ queue
async function loadQueue() {
  const st = $("#statusFilter").value;
  const rows = await api(`/api/alerts?status=${st}&limit=80`);
  $("#alertList").innerHTML = rows.map((a) => `<div class="alert" data-id="${a.alert_id}">
      <div><span class="badge b-${a.risk_band}">${a.risk_band}</span> <span class="amt">${gbp(a.amount_gbp, 2)}</span> → ${esc(a.payee_name)}</div>
      <div>${(+a.risk_score).toFixed(2)}</div>
      <div class="meta">${esc(a.suspected_scam_type || "–")} · ${esc(a.customer_display_name)} (${a.age_band}${a.vulnerability_flag ? ", vulnerable" : ""}) · ${a.legacy_rules_would_alert ? "rules also flagged" : "<b>missed by rules</b>"} · ${a.status}</div>
    </div>`).join("") || "<p class='muted' style='padding:16px'>No alerts in this state.</p>";
  $$(".alert").forEach((el) => el.addEventListener("click", () => { $$(".alert").forEach((x) => x.classList.remove("sel")); el.classList.add("sel"); showAlert(el.dataset.id); }));
}
$("#statusFilter").addEventListener("change", loadQueue);

async function showAlert(id) {
  const d = $("#alertDetail"); d.innerHTML = "<p class='muted'>Loading…</p>";
  const a = await api(`/api/alerts/${id}`);
  const script = (a.customer_call_script || "").split("|").map((s) => s.trim()).filter(Boolean);
  d.innerHTML = `
    <div><span class="badge b-${a.risk_band}">${a.risk_band} · ${(+a.risk_score).toFixed(3)}</span> <span class="badge b-rules">${a.legacy_rules_would_alert ? "Legacy rules: would alert" : "Legacy rules: MISSED"}</span> <span class="badge b-rules">${a.status}</span></div>
    <h2>${gbp(a.amount_gbp, 2)} to ${esc(a.payee_name)} <small class="muted">(${esc(a.payee_bank_name)})</small></h2>
    <div class="muted">${esc(a.alert_id)} · ${esc(a.payment_ts)} · SLA ${esc(a.sla_due_ts)}</div>
    <div class="facts">
      <div><span>Customer</span>${esc(a.customer_display_name)} · ${a.age_band}${a.vulnerability_flag ? " · vulnerable" : ""}</div>
      <div><span>Reference</span>"${esc(a.reference)}"</div><div><span>Channel</span>${a.channel}</div>
      <div><span>Confirmation of Payee</span>${a.cop_result}</div><div><span>New payee</span>${a.is_new_payee ? "yes, " + a.minutes_since_payee_added + " min ago" : "no"}</div>
      <div><span>On a phone call</span>${a.on_active_call ? "YES" : "no"}</div>
      <div><span>Receiving account age</span>${a.payee_account_age_days ?? "unknown"} days</div><div><span>Distinct senders 7d</span>${a.payee_distinct_senders_7d}</div>
      <div><span>× customer's 90d average</span>${a.amount_to_cust_avg_ratio ?? "–"}</div>
    </div>
    <div><b>Model reason codes</b><ul class="reasons">${parseReasons(a.reason_codes).map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>
    <div class="genai"><div class="tag">GenAI case note · ${esc(a.genai_model)} · confidence ${esc(a.genai_confidence)}</div>
      <p><b>Likely ${esc(a.suspected_scam_type)} scam.</b> ${esc(a.analyst_summary)}</p>
      <b>Ask the customer:</b><ul class="script">${script.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
      <div>Recommended: <b>${esc(a.recommended_action)}</b></div></div>
    <div class="actions">
      <button class="stop" data-d="CONFIRMED_SCAM_STOPPED">Confirmed scam: stop payment</button>
      <button class="warn" data-d="RELEASED_AFTER_WARNING">Release after warning</button>
      <button class="ok" data-d="RELEASED_GENUINE">Genuine: release</button>
      <button data-d="REFERRED_TO_POLICE">Refer to police</button>
      <button class="ghost" id="draftBtn" style="color:var(--ink)">Draft customer message (GenAI)</button>
    </div>
    <div id="draftOut"></div>
    <div style="margin-top:12px"><b>Decision log (Lakebase)</b>${(a.decisions || []).map((x) => `<div class="muted">${esc(x.created_at)} · ${esc(x.analyst)} · <b>${esc(x.decision)}</b> · ${gbp(x.amount_protected_gbp)} protected · ${esc(x.notes)}</div>`).join("") || "<div class='muted'>No decisions yet.</div>"}</div>`;
  $$(".actions button[data-d]", d).forEach((btn) => btn.addEventListener("click", async () => {
    btn.disabled = true;
    const notes = prompt("Notes for the case file (optional):", "") ?? "";
    await api(`/api/alerts/${id}/decision`, { method: "POST", body: JSON.stringify({ decision: btn.dataset.d, customer_contacted: true, notes }) });
    outcomeLoaded = false; await loadQueue(); showAlert(id);
  }));
  $("#draftBtn").addEventListener("click", async (e) => {
    e.target.disabled = true; $("#draftOut").innerHTML = "<p class='muted'>Drafting with GenAI…</p>";
    const r = await api(`/api/alerts/${id}/draft-followup`, { method: "POST" });
    $("#draftOut").innerHTML = `<div class="genai"><div class="tag">Draft · ${esc(r.model)}</div><p>${esc(r.draft).replace(/\n/g, "<br>")}</p></div>`;
    e.target.disabled = false;
  });
}

// ------------------------------------------------------------------ live check
let entitiesLoaded = false;
async function loadCheck() {
  if (entitiesLoaded) return; entitiesLoaded = true;
  const e = await api("/api/sample-entities");
  $("#custSel").innerHTML = e.customers.map((c) => `<option value="${c.customer_id}">${c.customer_id} · ${esc(c.customer_display_name)} · ${c.age_band}${c.vulnerability_flag ? " · vulnerable" : ""} · avg ${gbp(c.cust_avg_amount_90d)}</option>`).join("");
  $("#payeeSel").innerHTML = e.payees.map((p) => `<option value="${p.payee_id}">${p.payee_id} · ${esc(p.payee_name)} · ${esc(p.payee_bank_name)} (${p.payee_bank_type})${p.on_mule_watchlist ? " · ⚠ watchlist, " + p.payee_distinct_senders_7d + " senders/7d" : ""}</option>`).join("");
}
const PRESETS = {
  scam: { amount_gbp: 4800, reference: "safe account", channel: "MOBILE", cop_result: "NO_MATCH", payee_added_minutes_ago: 6, session_duration_sec: 420, on_active_call: true, payee: 0, cust: 0 },
  genuine: { amount_gbp: 1850, reference: "builder stage 2", channel: "WEB", cop_result: "MATCH", payee_added_minutes_ago: 2880, session_duration_sec: 75, on_active_call: false, payee: 3, cust: 3 },
};
$$("[data-preset]").forEach((b) => b.addEventListener("click", () => {
  const p = PRESETS[b.dataset.preset], f = $("#checkForm");
  for (const [k, v] of Object.entries(p)) { if (f.elements[k]) { if (f.elements[k].type === "checkbox") f.elements[k].checked = v; else f.elements[k].value = v; } }
  $("#payeeSel").selectedIndex = Math.min(p.payee, $("#payeeSel").options.length - 1);
  $("#custSel").selectedIndex = Math.min(p.cust, $("#custSel").options.length - 1);
}));
$("#checkForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, body = Object.fromEntries(new FormData(f).entries());
  body.on_active_call = f.elements.on_active_call.checked;
  ["amount_gbp", "payee_added_minutes_ago", "session_duration_sec"].forEach((k) => body[k] = Number(body[k]));
  const out = $("#checkResult"); out.innerHTML = "<p class='muted'>Scoring… (Lakebase lookup → Model Serving → GenAI)</p>";
  try {
    const r = await api("/api/check-payment", { method: "POST", body: JSON.stringify(body) });
    const colour = { CRITICAL: "var(--crit)", HIGH: "var(--warn)", MEDIUM: "var(--amber)", LOW: "var(--ok)" }[r.risk_band];
    out.innerHTML = `<h2 style="font-size:15px;margin:0 0 6px">Decision: ${esc(r.action.replaceAll("_", " "))}</h2>
      <div class="score" style="color:${colour}">${(r.risk_score * 100).toFixed(1)}<small style="font-size:16px"> /100 · ${r.risk_band}</small></div>
      <div class="lat">${Object.entries(r.latency_ms).map(([k, v]) => `<span>${k.replaceAll("_", " ")}: <b>${v} ms</b></span>`).join("")}</div>
      <b>Why</b><ul class="reasons">${(r.reason_codes || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      ${r.customer_warning ? `<div class="warnbox"><b>What the customer sees before confirming (GenAI)</b><p>${esc(r.customer_warning)}</p></div>` : "<p>No friction: payment released instantly.</p>"}
      <details><summary>Feature vector sent to the model (built from Lakebase lookups)</summary><pre class="sql">${esc(JSON.stringify(r.features, null, 2))}</pre></details>
      <p class="muted">Logged to Lakebase scam_ops.payment_checks #${r.check_id}</p>`;
  } catch (e) { out.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
});

// ------------------------------------------------------------------ genie
let convId = null;
const SUGGEST = ["What was the total confirmed APP scam value and our net reimbursement cost by scam type?",
  "How many alerts did the legacy rules raise per day compared with confirmed scams?",
  "Which receiving banks are linked to the most confirmed scam value?",
  "Show the top 10 mule-watchlist accounts by number of distinct senders",
  "What share of impersonation scam victims are aged 65 or over?"];
$("#suggest").innerHTML = SUGGEST.map((s) => `<button>${esc(s)}</button>`).join("");
$$("#suggest button").forEach((b) => b.addEventListener("click", () => { $("#genieQ").value = b.textContent; $("#genieForm").requestSubmit(); }));
$("#genieNew").addEventListener("click", () => { convId = null; $("#genieOut").innerHTML = ""; });
$("#genieForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("#genieQ").value.trim(); if (!q) return;
  const turn = document.createElement("div"); turn.className = "turn"; turn.innerHTML = `<div class="q">${esc(q)}</div><p class="muted">Genie is thinking…</p>`;
  $("#genieOut").prepend(turn);
  try {
    const r = await api("/api/genie", { method: "POST", body: JSON.stringify({ question: q, conversation_id: convId }) });
    convId = r.conversation_id;
    const table = r.columns.length ? `<table class="tbl"><tr>${r.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${r.rows.map((row) => `<tr>${row.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</table>` : "";
    turn.innerHTML = `<div class="q">${esc(q)}</div>${r.text ? `<p>${esc(r.text)}</p>` : ""}${r.description ? `<p class="muted">${esc(r.description)}</p>` : ""}${table}
      ${r.sql ? `<details><summary>Generated SQL (governed by Unity Catalog)</summary><pre class="sql">${esc(r.sql)}</pre></details>` : ""}`;
  } catch (e) { turn.innerHTML += `<p class="err">${esc(e.message)}</p>`; }
});

const loaders = { outcome: loadOutcome, queue: loadQueue, check: loadCheck, genie: () => {} };
window.addEventListener("load", () => loadOutcome().catch((e) => { $("#kpis").innerHTML = `<p class="err">${esc(e.message)}</p>`; }));
