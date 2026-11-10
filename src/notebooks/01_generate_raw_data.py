# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate raw synthetic data → UC Volume landing zone
# MAGIC
# MAGIC **Northbridge Bank** (fictional UK retail bank, 2.1M personal current-account customers).
# MAGIC This notebook simulates a **50,000-customer representative sample** and 90 days of outbound
# MAGIC Faster Payments, exactly as three source systems would drop them:
# MAGIC
# MAGIC | Source system | Landing path | Format | Cadence |
# MAGIC |---|---|---|---|
# MAGIC | Core banking (CRM) | `customers/`, `accounts/` | CSV | full extract |
# MAGIC | Payee / Confirmation-of-Payee intelligence | `payees/` | CSV | full extract |
# MAGIC | Payments hub (Faster Payments gateway) | `payments/payments_YYYY-MM-DD.json` | nested JSON lines | one file / business day |
# MAGIC | Complaints & reimbursement system | `scam_claims/claims_YYYY-MM-DD.csv` | CSV | one file / day |
# MAGIC
# MAGIC **Scam typologies** (PSR / UK Finance categories) are injected with realistic behavioural signatures:
# MAGIC purchase, impersonation (police/bank "safe account"), investment, romance, advance-fee, invoice/mandate redirection.
# MAGIC Money goes to **mule accounts** that receive from several victims. The model never sees a ground-truth flag –
# MAGIC labels only arrive via **customer scam claims**, reported days later (label lag), ~12% never reported,
# MAGIC and ~6% of claims are first-party "false" claims that get rejected.
# MAGIC
# MAGIC Deliberate **data-quality defects** (duplicates from at-least-once delivery, null/negative amounts) are injected
# MAGIC so the Lakeflow expectations have something to catch.
# MAGIC
# MAGIC The generator is deterministic (seeded) and **incremental**: it only writes day files that do not yet exist
# MAGIC up to `through_date`, so re-running with a later date simulates the next day's file arriving (Auto Loader picks up only the new file).

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_my49a8_catalog")
dbutils.widgets.text("raw_schema", "northbridge_raw")
dbutils.widgets.text("through_date", "2026-11-07")
CATALOG = dbutils.widgets.get("catalog")
RAW_SCHEMA = dbutils.widgets.get("raw_schema")
THROUGH_DATE = dbutils.widgets.get("through_date")
LANDING = f"/Volumes/{CATALOG}/{RAW_SCHEMA}/landing"
print(f"Landing zone: {LANDING}  | writing day files through {THROUGH_DATE}")

# COMMAND ----------

import os, json, math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date

SEED = 20261109
rng = np.random.default_rng(SEED)

WINDOW_START = date(2026, 8, 11)
N_DAYS = 90                                   # 2026-08-11 .. 2026-11-08
WINDOW_END = WINDOW_START + timedelta(days=N_DAYS - 1)
N_CUST = 50_000
N_LEGIT_PAYEES = 120_000
N_MULES = 1_100
N_EPISODES = 1_650
print(WINDOW_START, "->", WINDOW_END)

# COMMAND ----------

# MAGIC %md ## Customers & accounts (core banking extract)

# COMMAND ----------

FIRST = ["Oliver","Amelia","George","Isla","Harry","Ava","Noah","Mia","Jack","Ivy","Leo","Freya","Arthur","Lily","Muhammad","Florence",
         "Oscar","Grace","Charlie","Sophia","Thomas","Evie","Henry","Poppy","William","Ella","James","Rosie","Alfie","Emily","Aisha","Priya",
         "David","Margaret","Susan","Peter","Patricia","John","Barbara","Robert","Sandra","Michael","Linda","Fatima","Omar","Zara","Ewan","Morag"]
LAST = ["Smith","Jones","Taylor","Brown","Williams","Wilson","Johnson","Davies","Patel","Robinson","Wright","Thompson","Evans","Walker","White",
        "Roberts","Green","Hall","Thomas","Clarke","Jackson","Wood","Harris","Edwards","Turner","Martin","Cooper","Hill","Ward","Hughes","Khan",
        "Ali","Campbell","Stewart","MacDonald","Murray","Begum","Singh","Kaur","Morgan","Price","Lewis","Murphy","Kelly","O'Neill","Byrne"]
REGIONS = {  # region: (weight, outward postcode prefixes)
    "London": (0.17, ["E1","N7","SE15","SW9","W5","NW3","E17"]),
    "South East": (0.14, ["GU1","RG1","BN1","ME4","OX4","MK9"]),
    "North West": (0.11, ["M1","M20","L8","WA1","PR1","BL1"]),
    "West Midlands": (0.09, ["B1","B15","CV1","WV1","DY1"]),
    "Yorkshire and the Humber": (0.09, ["LS1","LS12","S1","BD1","HU1","YO1"]),
    "Scotland": (0.09, ["EH1","G1","G12","AB10","DD1","IV2"]),
    "East of England": (0.09, ["CB1","NR1","IP1","CM1","LU1"]),
    "South West": (0.08, ["BS1","EX4","PL1","BA1","TR1"]),
    "East Midlands": (0.07, ["NG1","LE1","DE1","LN1"]),
    "Wales": (0.05, ["CF10","SA1","LL11","NP20"]),
    "North East": (0.04, ["NE1","SR1","DH1","TS1"]),
}
region_names = list(REGIONS)
region_w = np.array([REGIONS[r][0] for r in region_names]); region_w /= region_w.sum()

cust_idx = np.arange(N_CUST)
customer_id = np.array([f"C{1000000 + i}" for i in cust_idx])
age = np.clip(rng.choice(np.arange(18, 92), size=N_CUST,
              p=(lambda a: a / a.sum())(np.interp(np.arange(18, 92), [18, 25, 35, 50, 65, 75, 91], [0.6, 1.0, 1.1, 1.0, 0.9, 0.6, 0.15]))), 18, 91)
dob = [WINDOW_END - timedelta(days=int(a * 365.25 + rng.integers(0, 365))) for a in age]
region = rng.choice(region_names, size=N_CUST, p=region_w)
postcode = [f"{rng.choice(REGIONS[r][1])} {rng.integers(1,10)}{chr(65+rng.integers(0,26))}{chr(65+rng.integers(0,26))}" for r in region]
first = rng.choice(FIRST, N_CUST); last = rng.choice(LAST, N_CUST)
full_name = np.char.add(np.char.add(first.astype(str), " "), last.astype(str))
email = [f"{f.lower()}.{l.lower().replace(chr(39),'')}{rng.integers(1,999)}@example.co.uk" for f, l in zip(first, last)]
phone = [f"07{rng.integers(100,999)} {rng.integers(100000,999999)}" for _ in cust_idx]
vuln_p = np.where(age >= 75, 0.22, np.where(age >= 65, 0.09, 0.04))
vulnerability_flag = rng.random(N_CUST) < vuln_p           # FCA Consumer Duty: customer with characteristics of vulnerability
tenure_months = np.clip((rng.gamma(2.0, 50, N_CUST)).astype(int), 1, 600)
digital_active = rng.random(N_CUST) < np.where(age >= 75, 0.55, 0.93)
income_scale = rng.lognormal(0, 0.45, N_CUST)               # relative spend level
segment = np.where(age < 24, "Student", np.where(age >= 66, "Senior", np.where(income_scale > 1.6, "Premier", "Everyday")))

customers = pd.DataFrame({
    "customer_id": customer_id, "full_name": full_name, "date_of_birth": [d.isoformat() for d in dob],
    "email": email, "mobile_phone": phone, "postcode": postcode, "region": region, "segment": segment,
    "vulnerability_flag": vulnerability_flag, "tenure_months": tenure_months, "digital_active": digital_active,
    "extract_ts": f"{WINDOW_END.isoformat()}T23:00:00Z",
})
account_id = np.array([f"A{30000000 + i}" for i in cust_idx])
accounts = pd.DataFrame({
    "account_id": account_id, "customer_id": customer_id,
    "sort_code": [f"30-{rng.integers(10,99)}-{rng.integers(10,99)}" for _ in cust_idx],
    "account_number": [f"{rng.integers(10000000, 99999999)}" for _ in cust_idx],
    "product": np.where(segment == "Premier", "Premier Current Account", np.where(segment == "Student", "Student Account", "Classic Current Account")),
    "opened_date": [(WINDOW_END - timedelta(days=int(t * 30.4))).isoformat() for t in tenure_months],
    "current_balance_gbp": np.round(rng.lognormal(7.6, 1.1, N_CUST) * income_scale, 2),
    "extract_ts": f"{WINDOW_END.isoformat()}T23:00:00Z",
})
customers.head(3)

# COMMAND ----------

# MAGIC %md ## Payees (beneficiaries) incl. hidden mule accounts

# COMMAND ----------

BANKS = [  # receiving PSP, type, share of legit payees, share of mule accounts
    ("Albion Bank", "HIGH_STREET", 0.20, 0.14), ("Crown & County", "HIGH_STREET", 0.16, 0.12), ("Thames Mutual", "BUILDING_SOCIETY", 0.10, 0.04),
    ("Caledonia Bank", "HIGH_STREET", 0.10, 0.08), ("Northbridge Bank", "HIGH_STREET", 0.09, 0.05), ("Monzo-like Neo", "CHALLENGER", 0.12, 0.18),
    ("Brightpay EMI", "EMI", 0.08, 0.17), ("Payflux EMI", "EMI", 0.05, 0.12), ("Unity Credit Union", "CREDIT_UNION", 0.04, 0.03),
    ("Starling-like Neo", "CHALLENGER", 0.06, 0.07),
]
bank_names = [b[0] for b in BANKS]; bank_type = {b[0]: b[1] for b in BANKS}
legit_bank_p = np.array([b[2] for b in BANKS]); legit_bank_p /= legit_bank_p.sum()
mule_bank_p = np.array([b[3] for b in BANKS]); mule_bank_p /= mule_bank_p.sum()

PAYEE_TYPES = {  # type: (share, lognormal mu, sigma) for legit amounts in GBP
    "individual": (0.46, 4.1, 0.9), "utility": (0.12, 4.0, 0.5), "landlord": (0.06, 6.8, 0.3), "merchant": (0.16, 4.3, 0.9),
    "trades": (0.08, 6.2, 0.8), "savings_investment": (0.06, 5.8, 0.9), "car_dealer": (0.02, 7.6, 0.8), "solicitor": (0.04, 7.0, 1.0),
}
ptypes = list(PAYEE_TYPES); ptype_p = np.array([PAYEE_TYPES[t][0] for t in ptypes]); ptype_p /= ptype_p.sum()
legit_type = rng.choice(ptypes, size=N_LEGIT_PAYEES, p=ptype_p)
legit_bank = rng.choice(bank_names, size=N_LEGIT_PAYEES, p=legit_bank_p)
legit_open = [WINDOW_START - timedelta(days=int(d)) if rng.random() > 0.08 else WINDOW_START - timedelta(days=int(rng.integers(5, 150)))
              for d in rng.gamma(2.2, 700, N_LEGIT_PAYEES) + 30]   # 8% of genuine payees are newly opened accounts too

mule_bank = rng.choice(bank_names, size=N_MULES, p=mule_bank_p)
# 55% freshly opened mule accounts, 45% "aged" accounts bought/rented from real people (harder to spot)
mule_open = [WINDOW_START + timedelta(days=int(d)) if rng.random() < 0.55 else WINDOW_START - timedelta(days=int(rng.integers(365, 2200)))
             for d in rng.integers(-70, 80, N_MULES)]

payee_id = np.array([f"P{2000000 + i}" for i in range(N_LEGIT_PAYEES + N_MULES)])
p_first = rng.choice(FIRST, N_LEGIT_PAYEES + N_MULES); p_last = rng.choice(LAST, N_LEGIT_PAYEES + N_MULES)
biz_suffix = {"utility": " Energy Ltd", "landlord": " Lettings", "merchant": " Retail Ltd", "trades": " Building Services",
              "savings_investment": " Capital", "car_dealer": " Motors", "solicitor": " & Co Solicitors"}
names = []
for i in range(N_LEGIT_PAYEES):
    t = legit_type[i]
    names.append(f"{p_first[i]} {p_last[i]}" if t == "individual" else f"{p_last[i]}{biz_suffix[t]}")
mule_is_business = rng.random(N_MULES) < 0.30          # some mules are shell / hijacked company accounts
for j in range(N_MULES):
    nm = f"{p_first[N_LEGIT_PAYEES + j]} {p_last[N_LEGIT_PAYEES + j]}"
    names.append(f"{p_last[N_LEGIT_PAYEES + j]} {rng.choice(['Capital', 'Trading Ltd', 'Building Services', 'Retail Ltd'])}" if mule_is_business[j] else nm)

all_open = legit_open + mule_open
intel_known = rng.random(N_LEGIT_PAYEES + N_MULES) > 0.30          # 30% of receiving accounts: no intel shared
payees = pd.DataFrame({
    "payee_id": payee_id,
    "payee_name": names,
    "payee_category": list(np.where(legit_type == "individual", "PERSON", "BUSINESS")) + list(np.where(mule_is_business, "BUSINESS", "PERSON")),
    "payee_bank_name": list(legit_bank) + list(mule_bank),
    "payee_bank_type": [bank_type[b] for b in list(legit_bank) + list(mule_bank)],
    "payee_sort_code": [f"{rng.integers(10,99)}-{rng.integers(10,99)}-{rng.integers(10,99)}" for _ in payee_id],
    "payee_account_opened_date": [d.isoformat() if k else None for d, k in zip(all_open, intel_known)],
    "intel_source": np.where(intel_known, "INTERBANK_DATA_SHARING", None),
    "extract_ts": f"{WINDOW_END.isoformat()}T23:00:00Z",
})
legit_payee_type = dict(zip(payee_id[:N_LEGIT_PAYEES], legit_type))
mule_ids = payee_id[N_LEGIT_PAYEES:]
mule_open_by_id = dict(zip(mule_ids, mule_open))
payees.tail(3)

# COMMAND ----------

# MAGIC %md ## Legitimate payments (vectorised)

# COMMAND ----------

LEGIT_REFS = ["", "rent", "Rent Nov", "dinner", "thanks!", "invoice 1043", "gas bill", "school trip", "birthday", "car deposit",
              "builder stage 2", "deposit", "holiday", "savings", "pocket money", "football subs", "loan repay", "wedding gift", "family",
              "ISA top up", "investment", "flight", "visa application", "trading 212 top up", "admin fee"]
HOUR_P = np.array([1,0.5,0.3,0.2,0.2,0.4,1,2.5,4,5,5.5,6,6.5,6,5.5,5.5,6,6.5,6.5,6,5,4,3,2], float); HOUR_P /= HOUR_P.sum()

rate = rng.gamma(2.0, 0.125, N_CUST)                         # payments / day / customer, mean 0.25
n_pay = rng.poisson(rate * N_DAYS)
c_idx = np.repeat(cust_idx, n_pay)
N_LEGIT = len(c_idx)
day_off = rng.integers(0, N_DAYS, N_LEGIT)
hour = rng.choice(24, N_LEGIT, p=HOUR_P)
sec = rng.integers(0, 3600, N_LEGIT)
event_ts = (pd.Timestamp(WINDOW_START) + pd.to_timedelta(day_off, "D") + pd.to_timedelta(hour, "h") + pd.to_timedelta(sec, "s"))

# habitual payees: 2-8 per customer drawn from legit pool
n_hab = rng.integers(2, 9, N_CUST)
hab = rng.integers(0, N_LEGIT_PAYEES, (N_CUST, 8))
pick = (rng.random(N_LEGIT) * n_hab[c_idx]).astype(int)
is_new = rng.random(N_LEGIT) < 0.09
payee_ix = np.where(is_new, rng.integers(0, N_LEGIT_PAYEES, N_LEGIT), hab[c_idx, pick])
p_ids = payee_id[payee_ix]
p_types = legit_type[payee_ix]
mu = np.array([PAYEE_TYPES[t][1] for t in ptypes]); sg = np.array([PAYEE_TYPES[t][2] for t in ptypes])
t_ix = pd.Series(p_types).map({t: i for i, t in enumerate(ptypes)}).to_numpy()
amount = rng.lognormal(mu[t_ix], sg[t_ix]) * income_scale[c_idx] ** 0.6
amount = np.where(is_new, amount * rng.lognormal(0.55, 0.75, N_LEGIT), amount)   # new payees skew larger (cars, builders, deposits)
amount = np.round(np.clip(amount, 1, 60_000), 2)
payee_added_ts = np.where(is_new, event_ts - pd.to_timedelta(rng.exponential(35, N_LEGIT).astype(int) + 1, "m"),
                          pd.Timestamp(WINDOW_START) - pd.to_timedelta(rng.integers(30, 2000, N_LEGIT), "D"))
cop = np.where(is_new, rng.choice(["MATCH","CLOSE_MATCH","NO_MATCH","UNAVAILABLE"], N_LEGIT, p=[0.80,0.09,0.06,0.05]),
               rng.choice(["MATCH","UNAVAILABLE"], N_LEGIT, p=[0.97,0.03]))
channel = rng.choice(["MOBILE","WEB","BRANCH","TELEPHONY"], N_LEGIT, p=[0.70,0.22,0.03,0.05])
legit = pd.DataFrame({
    "c": c_idx, "event_ts": event_ts, "payee_id": p_ids, "amount": amount, "payee_added_ts": pd.to_datetime(payee_added_ts),
    "cop": cop, "channel": channel,
    "device_age_days": np.where(rng.random(N_LEGIT) < 0.03, rng.integers(0, 3, N_LEGIT), rng.integers(30, 1500, N_LEGIT)),
    "session_sec": np.round(rng.lognormal(4.5, 0.75, N_LEGIT)).astype(int),
    "login_to_pay_sec": np.round(rng.lognormal(3.8, 0.75, N_LEGIT)).astype(int),
    "on_call": rng.random(N_LEGIT) < 0.04,
    "reference": rng.choice(LEGIT_REFS, N_LEGIT),
    "payment_type": rng.choice(["FPS_SINGLE","FPS_SINGLE","FPS_SINGLE","FPS_STANDING_ORDER"], N_LEGIT),
    "scam_episode": -1,
})
print(f"legit payments: {N_LEGIT:,}")

# COMMAND ----------

# MAGIC %md ## Scam episodes (APP fraud) – behavioural signatures per typology

# COMMAND ----------

SCAMS = {
 # type: share, victim age profile weight fn, n_payments range, amount (mu, sigma), on_call p, spread_days, refs
 "purchase":      dict(share=0.48, n=(1, 2),  mu=6.0, sg=0.9,  call=0.04, spread=2,  refs=["puppy deposit","iphone 15","ps5","concert tickets","car deposit","campervan deposit","sofa"]),
 "impersonation": dict(share=0.14, n=(1, 4),  mu=8.4, sg=0.8,  call=0.55, spread=0,  refs=["safe account","account transfer","security transfer","HMRC","fraud dept","case 4471"]),
 "investment":    dict(share=0.11, n=(2, 7),  mu=7.9, sg=0.9,  call=0.18, spread=35, refs=["crypto investment","trading account","BTC wallet top up","investment","platform fee"]),
 "romance":       dict(share=0.07, n=(3, 9),  mu=7.0, sg=0.8,  call=0.08, spread=45, refs=["for you","flight ticket","medical bills","love you","visa fee","customs"]),
 "advance_fee":   dict(share=0.12, n=(1, 3),  mu=5.6, sg=0.7,  call=0.10, spread=6,  refs=["release fee","loan fee","parcel customs","admin fee","prize tax"]),
 "invoice_redirection": dict(share=0.08, n=(1, 1), mu=8.2, sg=0.7, call=0.08, spread=0, refs=["invoice 2231","builder final","solicitor completion","stage payment"]),
}
stypes = list(SCAMS); sshare = np.array([SCAMS[s]["share"] for s in stypes]); sshare /= sshare.sum()

def victim_weights(stype):
    w = np.ones(N_CUST)
    if stype in ("impersonation", "romance"):
        w *= np.where(age >= 65, 3.0, np.where(age >= 50, 1.6, 0.6)); w *= np.where(vulnerability_flag, 3.0, 1.0)
    elif stype == "investment":
        w *= np.where((age >= 30) & (age <= 64), 2.0, 0.6) * income_scale
    elif stype == "purchase":
        w *= np.where(age <= 40, 2.2, 0.8)
    elif stype == "advance_fee":
        w *= np.where(vulnerability_flag, 2.0, 1.0)
    return w / w.sum()

rows = []
ep_types = rng.choice(stypes, N_EPISODES, p=sshare)
for e, st in enumerate(ep_types):
    cfg = SCAMS[st]
    v = rng.choice(N_CUST, p=victim_weights(st))
    start = pd.Timestamp(WINDOW_START) + pd.Timedelta(days=int(rng.integers(0, N_DAYS)), hours=int(rng.choice(24, p=HOUR_P)), minutes=int(rng.integers(0, 60)))
    eligible = [m for m in mule_ids if pd.Timestamp(mule_open_by_id[m]) <= start - pd.Timedelta(days=3)]
    mule = rng.choice(eligible if eligible else mule_ids)
    n = int(rng.integers(cfg["n"][0], cfg["n"][1] + 1))
    offs = np.sort(rng.uniform(0, max(cfg["spread"], 0.01), n)); offs[0] = 0.0
    added = start - pd.Timedelta(minutes=int(rng.exponential(25)) + 1)
    base = rng.lognormal(cfg["mu"], cfg["sg"]) * income_scale[v] ** 0.4
    for k in range(n):
        if cfg["spread"] == 0:
            ts = start + pd.Timedelta(minutes=int(k * rng.integers(8, 90)))
        else:
            ts = start + pd.Timedelta(days=float(offs[k]))
        amt = base * (1 + 0.6 * k if st in ("investment", "romance") else rng.uniform(0.6, 1.3))
        rows.append(dict(
            c=v, event_ts=ts, payee_id=mule, amount=round(float(np.clip(amt, 20, 84_000)), 2), payee_added_ts=added,
            cop=rng.choice(["MATCH","CLOSE_MATCH","NO_MATCH","UNAVAILABLE"], p=[0.55,0.18,0.17,0.10]),
            channel=rng.choice(["MOBILE","WEB","TELEPHONY"], p=[0.74,0.18,0.08]),
            device_age_days=int(rng.integers(0, 3)) if rng.random() < 0.05 else int(rng.integers(30, 1500)),
            session_sec=int(rng.lognormal(5.0, 0.8)), login_to_pay_sec=int(rng.lognormal(4.2, 0.8)),
            on_call=bool(rng.random() < cfg["call"]),
            reference=(rng.choice(cfg["refs"]) if rng.random() > 0.50 else rng.choice(LEGIT_REFS)),   # 50% coached to use innocent refs
            payment_type="FPS_SINGLE", scam_episode=e, scam_type=st,
        ))
        if rng.random() < 0.45:   # well-coached victim: behaviour indistinguishable from a genuine payment
            rows[-1].update(cop="MATCH", on_call=bool(rng.random() < 0.04), session_sec=int(rng.lognormal(4.5, 0.75)),
                            login_to_pay_sec=int(rng.lognormal(3.8, 0.75)), reference=rng.choice(LEGIT_REFS))
scam = pd.DataFrame(rows)
scam = scam[(scam.event_ts >= pd.Timestamp(WINDOW_START)) & (scam.event_ts < pd.Timestamp(WINDOW_END + timedelta(days=1)))]
print(f"scam payments: {len(scam):,} across {scam.scam_episode.nunique():,} episodes")
scam.groupby("scam_type").agg(payments=("amount", "size"), value_gbp=("amount", "sum"), median_gbp=("amount", "median")).round(0)

# COMMAND ----------

# MAGIC %md ## Assemble payments-hub records (nested JSON) + inject data-quality defects

# COMMAND ----------

pay = pd.concat([legit.assign(scam_type=None), scam], ignore_index=True).sort_values("event_ts").reset_index(drop=True)
pay["payment_id"] = [f"FP{26000000000 + i}" for i in range(len(pay))]
pay["customer_id"] = customer_id[pay.c]
pay["account_id"] = account_id[pay.c]
pay["device_id"] = [f"dev-{(c * 7919) % 999983:06d}" for c in pay.c]
pay.loc[pay.device_age_days < 3, "device_id"] = [f"dev-new-{i:07d}" for i in range((pay.device_age_days < 3).sum())]
pay["day"] = pay.event_ts.dt.date

# data-quality defects
dq = rng.random(len(pay))
pay["amount_out"] = pay.amount.astype(object)
pay.loc[dq < 0.0015, "amount_out"] = None
neg = (dq >= 0.0015) & (dq < 0.0025) & pay.scam_type.isna().to_numpy()
pay.loc[neg, "amount_out"] = -1.0 * pay.loc[neg, "amount"]
dups = pay.sample(frac=0.002, random_state=7)                        # at-least-once delivery duplicates
pay_out = pd.concat([pay, dups]).sort_values("event_ts")
pay_out = pay_out.merge(payees[["payee_id", "payee_name", "payee_sort_code", "payee_bank_name"]], on="payee_id", how="left")
print(f"rows to land (incl. {len(dups):,} duplicates, {int((dq < 0.0015).sum()):,} null amounts, {int(neg.sum()):,} negative amounts): {len(pay_out):,}")

def to_record(r):
    p = r
    return {
        "payment_id": r.payment_id,
        "event_ts": r.event_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payment_type": r.payment_type,
        "debtor": {"account_id": r.account_id, "customer_id": r.customer_id},
        "creditor": {"payee_id": r.payee_id, "name": p.payee_name, "sort_code": p.payee_sort_code, "bank_name": p.payee_bank_name},
        "amount": {"value": r.amount_out, "currency": "GBP"},
        "reference": r.reference,
        "payee_added_ts": pd.Timestamp(r.payee_added_ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "confirmation_of_payee": {"result": r.cop},
        "channel_context": {"channel": r.channel, "device_id": r.device_id, "device_age_days": int(r.device_age_days),
                            "session_duration_sec": int(r.session_sec), "login_to_payment_sec": int(r.login_to_pay_sec),
                            "on_active_call": bool(r.on_call)},
    }

# COMMAND ----------

# MAGIC %md ## Scam claims (labels arrive late, some never, some are false)

# COMMAND ----------

claims = []
ep = pay[pay.scam_episode >= 0].groupby("scam_episode")
cid = 0
for e, g in ep:
    if rng.random() < 0.12:     # never reported
        continue
    report_ts = g.event_ts.max() + pd.Timedelta(hours=float(rng.lognormal(math.log(96), 0.9)))
    cid += 1
    gross_neg = rng.random() < 0.02
    for _, r in g.iterrows():
        reimb = 0.0 if gross_neg else min(r.amount, 85_000.0)
        claims.append(dict(claim_id=f"CL{500000 + cid}", customer_id=r.customer_id, payment_id=r.payment_id,
                           reported_ts=report_ts, scam_type_reported=r.scam_type, claimed_amount_gbp=r.amount,
                           outcome="REJECTED" if gross_neg else "UPHELD", rejection_reason="GROSS_NEGLIGENCE" if gross_neg else None,
                           reimbursed_amount_gbp=round(reimb, 2), receiving_psp_contribution_gbp=round(reimb * 0.5, 2)))
# first-party / false claims on legitimate new-payee payments
fp = pay[pay.scam_type.isna() & (pay.payee_added_ts > pay.event_ts - pd.Timedelta(days=1))].sample(n=110, random_state=11)
for _, r in fp.iterrows():
    cid += 1
    claims.append(dict(claim_id=f"CL{500000 + cid}", customer_id=r.customer_id, payment_id=r.payment_id,
                       reported_ts=r.event_ts + pd.Timedelta(days=float(rng.uniform(2, 20))), scam_type_reported=rng.choice(["purchase", "investment"]),
                       claimed_amount_gbp=r.amount, outcome="REJECTED", rejection_reason="NOT_APP_SCAM_FIRST_PARTY",
                       reimbursed_amount_gbp=0.0, receiving_psp_contribution_gbp=0.0))
claims = pd.DataFrame(claims)
claims["report_day"] = claims.reported_ts.dt.date
print(f"claims lines: {len(claims):,}  | upheld lines: {(claims.outcome=='UPHELD').sum():,}")

# COMMAND ----------

# MAGIC %md ## Write to the landing volume (only missing files ≤ through_date)

# COMMAND ----------

through = date.fromisoformat(THROUGH_DATE)
for sub in ["customers", "accounts", "payees", "payments", "scam_claims"]:
    os.makedirs(f"{LANDING}/{sub}", exist_ok=True)

customers.to_csv(f"{LANDING}/customers/customers_{WINDOW_END}.csv", index=False)
accounts.to_csv(f"{LANDING}/accounts/accounts_{WINDOW_END}.csv", index=False)
payees.to_csv(f"{LANDING}/payees/payees_{WINDOW_END}.csv", index=False)

written_pay, written_claims, skipped = 0, 0, 0
by_day = {d: g for d, g in pay_out.groupby("day")}
for d in pd.date_range(WINDOW_START, min(through, WINDOW_END)).date:
    pf = f"{LANDING}/payments/payments_{d}.json"
    if os.path.exists(pf):
        skipped += 1
    else:
        day_rows = by_day.get(d, pay_out.iloc[0:0])
        with open(pf, "w") as fh:
            for r in day_rows.itertuples(index=False):
                fh.write(json.dumps(to_record(r)) + "\n")
        written_pay += 1
    cf = f"{LANDING}/scam_claims/claims_{d}.csv"
    if not os.path.exists(cf):
        c = claims[claims.report_day == d].drop(columns=["report_day"])
        if len(c):
            c.assign(reported_ts=c.reported_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")).to_csv(cf, index=False)
            written_claims += 1

print(f"payment day-files written: {written_pay}, already present (skipped): {skipped}, claim files written: {written_claims}")

# COMMAND ----------

summary = {
    "customers": len(customers), "accounts": len(accounts), "payees_total": len(payees), "mule_accounts_hidden": N_MULES,
    "payments_generated_incl_dupes": len(pay_out), "scam_payments": int(len(scam)), "scam_episodes": int(scam.scam_episode.nunique()),
    "scam_value_gbp": round(float(scam.amount.sum()), 2), "claim_lines": len(claims),
    "landing_files": {s: len(os.listdir(f"{LANDING}/{s}")) for s in ["customers", "accounts", "payees", "payments", "scam_claims"]},
}
print(json.dumps(summary, indent=2))
dbutils.notebook.exit(json.dumps(summary))
