"""Checks the data-editing rules on a throwaway copy of the data. Your real data is not touched.

Run:  python tests/test_site_store.py
"""
import os, shutil, sys, tempfile
from pathlib import Path

REAL = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
shutil.copytree(REAL / "data", TMP / "data")
os.environ["CLAUDE_PROJECT_DIR"] = str(TMP)          # point the store at the copy
sys.path.insert(0, str(REAL / "server"))
import site_store as st

checks = []
def check(name, cond):
    checks.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'}  {name}")

def refused(fn, *a, **k):
    try:
        fn(*a, **k)
        return []
    except st.ValidationError as e:
        return e.errors

check("store writes to the copy, not the real data", str(st.SITES_CSV).startswith(str(TMP)))

# a normal update, with circuit_status filled in from the dates
r = st.update_site("S072", {"circuit_delivered": "2026-11-17"}, by="test", reason="carrier confirmed")
s = next(x for x in st.load_sites() if x["site_id"] == "S072")
check("delivering a circuit saves the date", s["circuit_delivered"] == "2026-11-17")
check("circuit_status becomes Delivered by itself", s["circuit_status"] == "Delivered" and r["auto_filled"])
check("change is logged with old and new values",
      st.recent_changes(1)[0]["changes"]["circuit_status"] == {"from": "Overdue", "to": "Delivered"})

# bad values are refused and nothing is saved
before = st.SITES_CSV.read_text()
check("bad date refused", refused(st.update_site, "S073", {"hardware_eta": "next week"}, by="test"))
check("unknown status word refused", refused(st.update_site, "S073", {"install_status": "Done"}, by="test"))
check("unknown vendor refused", refused(st.update_site, "S073", {"install_vendor": "Acme"}, by="test"))
check("unknown field refused", refused(st.update_site, "S073", {"colour": "red"}, by="test"))
check("Live without a live_date refused", refused(st.update_site, "S073", {"install_status": "Live"}, by="test"))
check("Rescheduled without a reason refused", refused(st.update_site, "S074", {"install_status": "Rescheduled"}, by="test"))
check("unknown site refused", refused(st.update_site, "S999", {"site_ready": "Yes"}, by="test"))
check("site_id cannot be changed", refused(st.update_site, "S073", {"site_id": "S074"}, by="test"))
check("file unchanged after refused edits", st.SITES_CSV.read_text() == before)

# live_date marks the site Live
st.update_site("S059", {"live_date": "2026-11-16"}, by="test")
check("live_date makes the site Live", next(x for x in st.load_sites() if x["site_id"] == "S059")["install_status"] == "Live")
check("no-op update saves nothing", st.update_site("S059", {"live_date": "2026-11-16"}, by="test")["saved"] is False)

# adding a site
r = st.add_site({"name": "Denver Store #301", "city": "Denver", "state": "CO", "region": "Central", "wave": "15",
                 "go_live_target": "2027-01-25", "carrier": "Bluewave Telecom", "install_vendor": "NorthStar Install",
                 "circuit_ordered": "2026-12-11"}, by="test", reason="new store")
check("new site gets the next ID", r["site_id"] == "S201")
check("circuit_due defaults to 30 days after order", r["site"]["circuit_due"] == "2027-01-10")
check("new site starts Not started", r["site"]["install_status"] == "Not started")
check("201 sites after adding", len(st.load_sites()) == 201)
check("duplicate ID refused", refused(st.add_site, {**r["site"]}, by="test"))
check("missing required fields refused", refused(st.add_site, {"name": "X"}, by="test"))

shutil.rmtree(TMP)
print(f"\n{sum(checks)}/{len(checks)} data-editing checks passed")
sys.exit(0 if all(checks) else 1)
