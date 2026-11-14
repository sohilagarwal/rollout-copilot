"""Checks the tools themselves, without the AI. Fast and free.

Run:  python tests/test_tools.py
If these pass and an eval fails, the problem is in how the AI used the tools,
not in the tools.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import rollout_server as r

checks = []
def check(name, cond):
    checks.append(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}")

s = r.program_summary()
check("200 sites loaded", s["total_sites"] == 200)
check("51 sites live", s["live"] == 51)
check("30 sites at risk in 21 days", r.at_risk_sites(21)["count"] == 30)
check("8 circuits still overdue", s["circuits_overdue"] == 8)
sc = r.vendor_scorecard()
check("NorthStar first-time success 74%", sc["install_vendors"]["NorthStar Install"]["first_time_success_rate"] == "74%")
check("Cascade on-time 52%", sc["carriers"]["Cascade Fiber"]["on_time_rate"] == "52%")
check("search finds the late credit clause", "4.2" in r.search_docs("late delivery credit")["results"][0]["section"])
check("search finds the router backorder email", "router" in r.search_docs("router backorder")["results"][0]["source"])
check("unknown site gives an error, not data", "error" in r.get_site("S250"))
d = r.draft_email("test@example.com", "Test draft", "Hello", "S001")
check("draft_email never sends", d["sent"] is False)
(r.PROJECT / d["saved"]).unlink()

print(f"\n{sum(checks)}/{len(checks)} tool checks passed")
sys.exit(0 if all(checks) else 1)
