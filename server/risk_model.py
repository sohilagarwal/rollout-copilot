"""Abort risk score: how likely is a site's first technician visit to fail?

Each risk factor gets a chance of causing a failed visit. The vendor and carrier chances are
learned from this program's own history; the rest are fixed assumptions written down in
docs/risk_model.md. The factors are combined as independent chances:

    risk = 1 - (1 - p1) x (1 - p2) x ...

so every score can be explained factor by factor. backtest() checks the score against
visits that already happened, using only what was known before each visit.
"""
from collections import defaultdict
from datetime import date, timedelta

HIGH, MEDIUM = 0.60, 0.30

# fixed assumptions (see docs/risk_model.md)
P_CIRCUIT_OVERDUE = 0.90        # circuit already past due: visit almost surely fails
P_CIRCUIT_TOO_CLOSE = 0.60      # circuit due less than 5 days before go-live
SHARE_LATE_ENOUGH = 0.50        # of late circuits, the share late enough to miss go-live
P_HW_LATE = 0.90                # hardware arrives after the visit
P_HW_BACKORDERED = 0.30         # backordered, but due to arrive in time
P_HW_NOT_SHIPPED_CLOSE = 0.30   # not shipped within 10 days of go-live
P_SITE_NOT_READY = 0.90
P_SITE_UNCONFIRMED_CLOSE = 0.30
P_NO_TECH_CLOSE = 0.50
P_PREVIOUS_ABORT = 0.20

def _d(s):
    return date.fromisoformat(s) if s else None

def visited(sites, today):
    return [s for s in sites if int(s["install_attempts"]) >= 1 and _d(s["go_live_target"]) < today]

def first_visit_failed(s):
    return not (int(s["install_attempts"]) == 1 and s["install_status"] == "Live")

def learned_rates(sites, today, leave_out=None):
    """Vendor: share of first visits that failed for reasons other than a missing circuit
    (the circuit factor covers that). Carrier: share of circuits due so far that came late."""
    v_n, v_fail, c_n, c_late = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for s in visited(sites, today):
        if s["site_id"] == leave_out or s["last_abort_reason"] == "Circuit not active":
            continue
        v_n[s["install_vendor"]] += 1
        v_fail[s["install_vendor"]] += first_visit_failed(s)
    for s in sites:
        if s["site_id"] == leave_out or _d(s["circuit_due"]) > today:
            continue
        c_n[s["carrier"]] += 1
        got = _d(s["circuit_delivered"])
        c_late[s["carrier"]] += (got is None) or got > _d(s["circuit_due"])
    vendor = {v: v_fail[v] / v_n[v] for v in v_n}
    carrier = {c: c_late[c] / c_n[c] for c in c_n}
    return vendor, carrier

def band(p):
    return "High" if p >= HIGH else "Medium" if p >= MEDIUM else "Low"

def combine(factors):
    keep = 1.0
    for _, p in factors:
        keep *= 1 - p
    return 1 - keep

def score(s, today, vendor_rate, carrier_rate):
    """Risk for a site not yet live. Returns (risk, [(factor, chance), ...])."""
    go = _d(s["go_live_target"])
    days = (go - today).days
    f = [(f"{s['install_vendor']} first-visit failure rate", vendor_rate.get(s["install_vendor"], 0.1))]
    if s["circuit_status"] != "Delivered":
        due = _d(s["circuit_due"])
        if due < today:
            f.append(("Circuit already overdue", P_CIRCUIT_OVERDUE))
        elif due > go - timedelta(days=5):
            f.append(("Circuit due less than 5 days before go-live", P_CIRCUIT_TOO_CLOSE))
        else:
            f.append((f"{s['carrier']} late-delivery rate", carrier_rate.get(s["carrier"], 0.2) * SHARE_LATE_ENOUGH))
    eta = _d(s["hardware_eta"])
    if s["hardware_status"] == "Backordered":
        f.append(("Hardware backordered past go-live", P_HW_LATE) if eta and eta > go - timedelta(days=3)
                 else ("Hardware backordered", P_HW_BACKORDERED))
    elif s["hardware_status"] == "Not shipped" and days <= 10:
        f.append(("Hardware not shipped, go-live within 10 days", P_HW_NOT_SHIPPED_CLOSE))
    if s["site_ready"] == "No":
        f.append(("Store says not ready", P_SITE_NOT_READY))
    elif s["site_ready"] != "Yes" and days <= 10:
        f.append(("Store readiness not confirmed, go-live within 10 days", P_SITE_UNCONFIRMED_CLOSE))
    if not s["technician_date"] and days <= 7:
        f.append(("No technician booked, go-live within 7 days", P_NO_TECH_CLOSE))
    if s["install_status"] == "Rescheduled":
        f.append(("Previous visit aborted", P_PREVIOUS_ABORT))
    f = [(name, round(p, 3)) for name, p in f if p > 0]
    return round(combine(f), 3), f

def backtest(sites, today):
    """Score every past first visit using only what was known before it, and compare with
    what happened. Vendor and carrier rates leave the site itself out (no peeking)."""
    rows = []
    for s in visited(sites, today):
        go = _d(s["go_live_target"])
        vendor, _ = learned_rates(sites, today, leave_out=s["site_id"])
        f = [("vendor", vendor.get(s["install_vendor"], 0.1))]
        got = _d(s["circuit_delivered"])
        if got is None or got > go - timedelta(days=5):   # circuit missing 5 days before the visit
            f.append(("circuit", P_CIRCUIT_OVERDUE))
        rows.append((combine(f), first_visit_failed(s)))
    out = {}
    for b in ("High", "Medium", "Low"):
        grp = [failed for p, failed in rows if band(p) == b]
        out[b] = {"visits": len(grp), "failed": sum(grp),
                  "failure_rate": f"{100 * sum(grp) / len(grp):.0f}%" if grp else "n/a"}
    failures = sum(f for _, f in rows)
    caught = sum(f for p, f in rows if band(p) != "Low")
    flagged = sum(1 for p, _ in rows if band(p) != "Low")
    return {"past_first_visits": len(rows), "failed": failures, "by_band": out,
            "failures_flagged_medium_or_high": f"{caught} of {failures}",
            "precision_of_medium_or_high": f"{100 * caught / flagged:.0f}%" if flagged else "n/a",
            "overall_failure_rate": f"{100 * failures / len(rows):.0f}%" if rows else "n/a"}
