# 1 · Stop the scam, not the customer

**Northbridge Bank · Fraud Strategy & Operations · Proposal to the Executive Committee**

* **£2.7m net annual value** (range £1.0m to £4.1m), mostly from APP-scam reimbursement cost Northbridge stops paying
* **94% of scam value intercepted** with the *same* number of payment holds (today: 58%)
* **13.7 → 2.2 genuine customers held per scam caught**: fewer good customers blocked
* **29,200 analyst hours released per year** through GenAI case notes and call scripts
* Working prototype on Databricks today; a 6-week shadow-mode pilot proves it on Northbridge's own data

> Synthetic data. Northbridge is a fictional UK retail bank (2.1M current-account customers). Model results are measured on a hold-out window. Bank-level £ figures apply those measured rates to published UK baselines. Every assumption is listed on slide 5.

---

# 2 · Why now: the PSR made APP scams a P&L line

* Since **7 Oct 2024**, UK banks **must reimburse** APP-scam victims, **up to £85,000 per claim**. The sending and receiving bank **split the cost 50:50**.
* UK APP-scam losses in 2024: **£450.7m** across **185,733 cases** (UK Finance, Annual Fraud Report 2025).
* PSR one-year update: **88% of losses on reimbursable claims returned** to victims (£112m in the first nine months).
* For Northbridge (≈2.6% of UK current accounts) that is **≈£11.7m of customer losses a year**, and roughly half of what's reimbursed now sits on our P&L.
* Today's control is a 3-condition rules engine. On our hold-out test it holds **1,533 payments to catch 58% of scam value**, with a hit-rate of **6.8%**. Most holds are genuine customers. Small purchase scams (half of all cases) go straight through.
* Consumer Duty raises the bar on *both* sides: protect vulnerable customers, and don't add needless friction for everyone else.

---

# 3 · What changes, for whom

| | **Executive sponsor**: Chief Risk Officer / COO | **Domain owner**: Head of Fraud Operations |
|---|---|---|
| Today | Reimbursement liability growing, hard to forecast; regulator scrutiny on outcomes | A fixed team buried in false-positive holds; 11 minutes per case gathering evidence |
| With Scam Shield | **£1.7m/yr less net reimbursement cost**; one governed set of numbers for ExCo, the PSR and the board | **Same team, 94% of scam value caught**; every alert arrives with reason codes, a GenAI case note and a Consumer-Duty-safe call script |
| KPI moved | Net APP reimbursement cost (£), customer losses prevented (£), complaints | Value recall, precision (genuine holds per scam), minutes per case, SLA within 4 h |
| Proof | Business case on slide 5; measured on hold-out | Live queue in the app; decisions logged and fed back into the model |

---

# 4 · Results on the hold-out test (10–29 Oct 2026, same alert budget)

| Measure | Legacy rules | ML model | Change |
|---|---|---|---|
| Payments held | 1,533 | 1,533 | same budget |
| Scam value intercepted | 58% | **94%** | **+36 pts** |
| Scams caught (count) | 17% | **78%** | small purchase scams now caught |
| Hit-rate (precision) | 6.8% | **31.4%** | 4.6× better |
| Genuine customers held per scam | 13.7 | **2.2** | less friction |
| Holds needed to match today's catch | 1,533 | **168** | **−89%** |

PR-AUC 0.609 · ROC-AUC 0.996 · LightGBM · value-weighted · time-based split · model v5 in Unity Catalog (`@champion`)

| Scam type | Scam payments | Scam value | Rules value recall | Model value recall |
|---|---|---|---|---|
| investment | 117 | £1.4m | 69% | 98% |
| romance | 106 | £364,199 | 10% | 99% |
| impersonation | 74 | £327,568 | 83% | 90% |
| purchase | 240 | £136,381 | 9% | 71% |
| invoice_redirection | 24 | £94,032 | 78% | 75% |
| advance_fee | 56 | £19,596 | 0% | 69% |

---

# 5 · Business case (annual, Northbridge)

| Line | Value | Basis |
|---|---|---|
| Scam value held by today's rules (hold-out test) | 58.3% | Measured: model_evaluation, same alert budget |
| Scam value held by ML model (hold-out test) | 94.5% | Measured: model_evaluation, same alert budget |
| Northbridge APP scam losses today (per year) | £11.7m | UK Finance 2024 APP losses GBP 450.7m x 2.6% PCA share (assumption) |
| Implied attempted scam value (per year) | £18.0m | losses / (1 - rules recall x 60% intervention success) |
| Customer losses prevented (per year) | £3.9m | attempted x (model recall - rules recall) x intervention success |
| Northbridge net reimbursement cost avoided | £1.7m | prevented x 88% reimbursed (PSR) x 50% after receiving-PSP share |
| Analyst hours released (per year) | 29,200.0 | 1,200 holds/day x (11 -> 7 min) with GenAI case notes |
| Value of analyst capacity released | £1.1m | hours x GBP 38/h loaded cost (redeploy to complex cases) |
| Genuine customers held per scam caught: rules | 13.7 | Measured: 1/precision - 1 |
| Genuine customers held per scam caught: model | 2.2 | Measured: Consumer Duty friction indicator |
| Platform run cost (per year) | £-180,000 | Estimate: serverless pipeline + Lakebase + serving + FMAPI + app |
| **Net annual value to Northbridge** | £2.7m | net reimbursement avoided + analyst capacity - run cost |

**Sensitivity:** model uplift held at its measured value; only the unvalidated assumptions move.

| Scenario | UK PCA share | Intervention success | Minutes saved / case | Run cost | Customer losses prevented | **Net annual value** | ROI |
|---|---|---|---|---|---|---|---|
| Conservative | 2.0% | 40% | 2 | £300,000 | £1.7m | **£1.0m** | 4x |
| Base (headline) | 2.6% | 60% | 4 | £180,000 | £3.9m | **£2.7m** | 16x |
| Upside | 3.0% | 75% | 5 | £150,000 | £6.5m | **£4.1m** | 28x |

**ROI ≈ 16× run cost · payback ≈ 0.8 months.** Assumptions marked as assumptions are validated in the pilot; measured figures come from the hold-out test.

---

# 6 · How it works: one governed journey, not five demos

```
Raw files ──▶ Lakeflow pipeline ──▶ Unity Catalog ──▶ ML + GenAI ──▶ Lakebase ──▶ Scam Shield app
(payments,     bronze→silver→gold    masks · tags ·    risk model     operational   Outcome · Queue ·
 claims,       expectations ·        lineage ·         + reason       store: queue,  Live check · Genie
 customers)    de-dup · quarantine   metric view       codes · Claude decisions, ◀─── Lakehouse Sync back to UC
                                                       case notes     profiles        → Genie + retraining labels
```

* **Lakeflow**: Auto Loader + declarative pipeline, 7 data-quality expectations, a quarantine table, AUTO CDC de-duplication
* **Unity Catalog**: PII masked at source for everyone outside `northbridge-pii-readers` (including the AI); governed tags; automatic lineage; one metric view for every KPI
* **ML + GenAI**: a UC-registered model behind a real-time serving endpoint; Claude writes the case note, the call script and the customer warning
* **Lakebase**: millisecond lookups + transactional analyst decisions; decisions stream back to the lakehouse automatically
* **Genie**: the Head of Fraud asks questions in plain English over the same governed data
* **One bundle, one job**: reproducible, promotable to production

**Proof it's one journey:** payment `FP26001105668` (£8,552 to a 41-day-old EMI account) was *not* flagged by the legacy rules. The model scored it **CRITICAL 0.999**, Claude wrote the case note, an analyst stopped it in the app, and the decision flowed back into Unity Catalog seconds later. Every hop is shown with a query in `evidence/trace_one_payment.md`.

---

# 7 · What you'll see in the demo (tell → show → tell)

1. **Outcome**: model vs rules, £ business case, live ops counters
2. **Analyst queue**: a £-thousands "safe account" payment the rules **missed**; reason codes; GenAI case note and call script; one click records the decision (Lakebase)
3. **Live payment check**: the same customer pays a mule account. Lakebase lookups → model → "Pause and check" warning written by GenAI, in about a second
4. **Ask Genie**: "Which scam type cost us most in net reimbursement?" and a follow-up, with the SQL shown

---

# 8 · Governance, model risk and Consumer Duty

* **PRA SS1/23 model risk**: model inventory in UC, versioned with `@champion`, hold-out evaluation stored as a table, lineage from raw file to score, inference tables log every real-time decision
* **Explainability**: top-3 reason codes on every score, in plain English for analysts and customers
* **Human in the loop**: the model *holds and explains*; an analyst decides. Every decision is audited in Lakebase and in UC history
* **Data minimisation**: the operational store only gets masked names; Genie has PII columns excluded *and* masked
* **GenAI guardrails**: low temperature, strict JSON schema, non-accusatory open questions, failures logged and never blocking

---

# 9 · Decisions & trade-offs (summary)

* **Same-alert-budget comparison**, not AUC: it answers "more £ caught with the same team?"
* **Lakebase for the app, the warehouse for analytics**: point reads and transactions vs scans
* **Batch GenAI (Haiku) + interactive GenAI (Sonnet)**: cost where it's cheap, quality where it's customer-facing
* **Feature parity by code today; online feature serving in production**
* **Synthetic, scam-enriched data**: so we apply *rates*, not totals, to the business case. Re-measured in the pilot.

Full list: `docs/decisions-and-tradeoffs.md`

---

# 10 · Pilot: 6 weeks, shadow mode, no customer impact

| Week | Activity | Exit criterion |
|---|---|---|
| 1–2 | Land 12 months of Northbridge payments + claims via Lakeflow; UC masks & grants with Security | Data reconciled with finance (claims £) within 1% |
| 3–4 | Retrain on Northbridge history; shadow-score live payments (no holds) | Value recall ≥ rules + 15 pts at equal holds |
| 5 | Analysts work the shadow queue in the app; GenAI notes evaluated by QA | ≥ 25% handling-time reduction; zero non-compliant scripts |
| 6 | Model risk validation pack (SS1/23); ExCo go/no-go | Signed-off business case |

**What we need from Northbridge:** a data owner from Fraud Ops, read access to the payments hub and complaints feeds, 2 analysts for week 5, and a model risk reviewer.

---

# 11 · Likely objections, and answers

| Objection | Answer |
|---|---|
| "These are synthetic numbers." | Yes. That's why the business case applies *measured rates* to public baselines, and why the pilot re-measures on your data before go-live. |
| "Won't more holds annoy customers?" | Same number of holds, and 13.7 → 2.2 genuine customers per scam caught. Friction goes *down*. |
| "Can we explain a decline to the FOS?" | Every score carries reason codes; every analyst decision is time-stamped with the analyst and notes. |
| "Is GenAI safe in front of customers?" | It drafts; humans approve. Prompts enforce non-accusatory language. Outputs are logged and evaluated. |
| "Another database to run?" | Lakebase is serverless Postgres inside the same governance; sync both ways is managed, so there's no ETL to build. |
| "Lock-in?" | Delta/Parquet, open Postgres, MLflow, standard SQL. |

---

# 12 · The ask

* **Approve a 6-week shadow-mode pilot** (Fraud Ops + Data + Model Risk)
* **Success = +15 pts value recall at equal holds and −25% handling time**, measured on Northbridge data
* **Decision at week 6**: production rollout plan, with real-time scoring in the payments journey
