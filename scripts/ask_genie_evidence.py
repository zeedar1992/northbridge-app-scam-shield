#!/usr/bin/env python3
"""Ask the deployed Genie Agent business questions (incl. a follow-up) and commit transcripts as Markdown.

Usage: python3 scripts/ask_genie_evidence.py <space_id> [--profile P] [--out evidence/genie_transcripts.md]
"""
import argparse
import json
import pathlib
import subprocess
from datetime import datetime, timezone

QUESTIONS = [
    ["Which scam type cost Northbridge the most in net reimbursement, and how much?"],
    ["How much more scam value does the ML model catch than the legacy rules engine at the same alert budget?",
     "And what does that mean for precision - how many genuine customers do we hold per scam caught under each approach?"],
    ["Which receiving banks received the most confirmed scam value? Show bank type too."],
    ["Show the top 5 mule watchlist accounts by number of distinct senders in 90 days"],
    ["What share of impersonation scam value came from customers aged 65 or over?"],
    ["How many alerts in the analyst queue are recommended HOLD_AND_CALL, and how many of those would the legacy rules have missed?"],
    ["How many case decisions have analysts recorded so far and how much money was protected?"],
    ["What is the net annual value in the business case and what are its main components?"],
]


def cli(args, profile):
    r = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:500])
    return json.loads(r.stdout)


def render(space, msg, profile):
    out = []
    for att in msg.get("attachments") or []:
        if att.get("text", {}).get("content"):
            out.append("**Genie:** " + att["text"]["content"].strip())
        if att.get("query"):
            qd = att["query"]
            if qd.get("description"):
                out.append("_" + qd["description"].strip() + "_")
            out.append("```sql\n" + qd.get("query", "").strip() + "\n```")
            try:
                res = cli(["genie", "get-message-attachment-query-result", space, msg["conversation_id"], msg["message_id"], att["attachment_id"]], profile)
                sr = res.get("statement_response", {})
                cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                rows = (sr.get("result") or {}).get("data_array") or []
                if cols:
                    out.append("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" +
                               "\n".join("| " + " | ".join(str(v) for v in r) + " |" for r in rows[:15]))
            except Exception as e:  # noqa: BLE001
                out.append(f"> result fetch error: {e}")
    return "\n\n".join(out) or f"> status: {msg.get('status')}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("space_id")
    ap.add_argument("--profile", default="fevm-serverless-stable-my49a8")
    ap.add_argument("--out", default="evidence/genie_transcripts.md")
    a = ap.parse_args()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = ["# Genie Agent transcripts: \"Northbridge APP Scam Analyst\"", "",
          f"Captured {now} via the Genie Conversation API (`databricks genie start-conversation` / `create-message`), space `{a.space_id}`.",
          "Each answer shows Genie's text, the SQL it generated against the governed Unity Catalog tables/metric view, and the returned rows.", ""]
    for i, thread in enumerate(QUESTIONS, 1):
        conv = None
        for j, q in enumerate(thread):
            if conv is None:
                msg = cli(["genie", "start-conversation", a.space_id, q], a.profile)
                conv = msg["conversation_id"]
            else:
                msg = cli(["genie", "create-message", a.space_id, conv, q], a.profile)
            md += [f"## Q{i}{'.' + str(j + 1) if len(thread) > 1 else ''}. {q}", "", render(a.space_id, msg, a.profile), ""]
            print("asked:", q[:70], "->", msg.get("status"))
    pathlib.Path(a.out).write_text("\n".join(md))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
