"""Approve or reject change requests from the terminal.

  python server/decide.py                          list pending requests
  python server/decide.py approve CR-001 --by "Sohil"
  python server/decide.py reject CR-002 --by "Sohil" --note "Store reopens sooner"

You can also approve in the web GUI (Approvals tab), or tell Claude "approve CR-001":
Claude Code then asks you to confirm before the change is applied.
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_requests as cr, site_store as st

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("action", nargs="?", choices=["approve", "reject"])
p.add_argument("request_id", nargs="?")
p.add_argument("--by", default="")
p.add_argument("--note", default="")
a = p.parse_args()

if not a.action:
    pending = cr.list_requests("pending")
    if not pending:
        print("No change requests waiting.")
    for r in pending:
        moves = "; ".join(f"{k}: {v['from'] or '-'} -> {v['to'] or '-'}" for k, v in r["diff"].items())
        print(f"{r['id']}  {r['site_id']}  {moves}\n        why: {r['reason']}\n        impact: {r['impact'] or '-'}\n")
    sys.exit(0)

try:
    r = cr.decide(a.request_id or "", a.action == "approve", by=a.by or input("Your name: "), note=a.note)
except st.ValidationError as e:
    sys.exit("Not done: " + "; ".join(e.errors))
print(f"{r['id']} {r['status']}." + (f" Changed: {', '.join(r['applied'])}" if r["applied"] else "") +
      (f" {r['decision_note']}" if r["decision_note"] else ""))
