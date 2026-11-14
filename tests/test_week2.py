"""Checks change requests and the risk score on a throwaway copy of the data.
Your real data is not touched.

Run:  python tests/test_week2.py
"""
import os, shutil, sys, tempfile
from pathlib import Path

REAL = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(REAL / "data", TMP / "data")
shutil.copytree(REAL / "docs", TMP / "docs")
(TMP / "data" / "change_requests.json").unlink(missing_ok=True)
os.environ["CLAUDE_PROJECT_DIR"] = str(TMP)
sys.path.insert(0, str(REAL / "server"))
import rollout_server as r, change_requests as cr, site_store as st

checks = []
def check(name, cond):
    checks.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'}  {name}")

site = lambda sid: next(x for x in st.load_sites() if x["site_id"] == sid)
check("works on the copy, not the real data", str(cr.REQUESTS).startswith(str(TMP)))
f = r.risk_forecast(21)   # scored before the changes below move any dates

# commitments can't be edited directly
res = r.update_site("S073", {"go_live_target": "2026-12-15"}, reason="routers late")
check("update_site refuses a go-live change", res["saved"] is False and "propose_change" in res["errors"][0])
check("go-live unchanged after refusal", site("S073")["go_live_target"] == "2026-11-23")

# propose: checked, filed, nothing applied
bad = r.propose_change("S073", {"go_live_target": "mid December"}, reason="routers late")
check("a bad date is refused when proposing", bad.get("filed") is False)
req = r.propose_change("S073", {"go_live_target": "2026-12-15"}, reason="Routers arrive 2026-12-04", impact="Wave 6 slips")
check("proposal filed as pending", req["id"] == "CR-001" and req["status"] == "pending")
check("proposal does not change the tracker", site("S073")["go_live_target"] == "2026-11-23")
dup = r.propose_change("S073", {"go_live_target": "2026-12-15"}, reason="again")
check("the same proposal twice is not filed twice", dup["id"] == "CR-001")
check("pending list shows it", r.list_change_requests("pending")["count"] == 1)

# decide
check("a decision must be approve or reject", r.decide_change_request("CR-001", "maybe", "Sohil")["done"] is False)
ok = r.decide_change_request("CR-001", "approve", "Sohil")
check("approval applies the change", ok["status"] == "approved" and site("S073")["go_live_target"] == "2026-12-15")
check("approval is logged with who approved", "approved CR-001" in st.recent_changes(1)[0]["by"])
check("a request can't be decided twice", r.decide_change_request("CR-001", "reject", "Sohil")["done"] is False)
r.propose_change("S081", {"go_live_target": "2026-12-14"}, reason="Store remodel")
no = r.decide_change_request("CR-002", "reject", "Sohil", note="Store reopens sooner")
check("rejection leaves the tracker alone", no["status"] == "rejected" and site("S081")["go_live_target"] == "2026-11-23")

# risk score
check("risk forecast scores every not-live site due in 21 days", f["sites_scored"] == 61)
check("highest-risk site is a backorder site", "backordered" in " ".join(f["sites"][0]["factors"]).lower())
check("NorthStar has the highest learned vendor failure rate",
      max(f["learned_rates"]["install_vendor_first_visit_failure"].items(), key=lambda kv: int(kv[1][:-1]))[0] == "NorthStar Install")
bt = f["backtest"]
check("backtest: High-risk visits failed far more than Low-risk",
      int(bt["by_band"]["High"]["failure_rate"][:-1]) > 3 * int(bt["by_band"]["Low"]["failure_rate"][:-1]))
check("the model card is searchable", "risk_model.md" in r.search_docs("risk score assumptions")["results"][0]["source"])

print(f"\n{sum(checks)}/{len(checks)} week 2 checks passed")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(checks) else 1)
