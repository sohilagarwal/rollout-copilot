"""Creates the sample rollout data: 200 sites, vendors, and vendor emails.

The data is fake but built like a real multi-site network rollout. A few
problems are planted on purpose so the AI has something real to find:
  - Cascade Fiber delivers circuits late more often than Bluewave Telecom.
  - NorthStar Install has a higher rate of aborted installs.
  - A router backorder hits a group of sites in the next few weeks.

Run it again any time to rebuild the same data:  python data/generate_data.py
"""
import csv, json, random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODAY = date(2026, 11, 16)          # the program's "today", fixed so answers are repeatable
random.seed(7)

CITIES = {
    "West":    [("San Jose","CA"),("Fresno","CA"),("Sacramento","CA"),("Reno","NV"),("Portland","OR"),("Boise","ID"),("Phoenix","AZ"),("Tucson","AZ")],
    "Central": [("Denver","CO"),("Dallas","TX"),("Austin","TX"),("Omaha","NE"),("Kansas City","MO"),("Tulsa","OK"),("Chicago","IL"),("Madison","WI")],
    "East":    [("Atlanta","GA"),("Charlotte","NC"),("Richmond","VA"),("Baltimore","MD"),("Pittsburgh","PA"),("Columbus","OH"),("Tampa","FL"),("Nashville","TN")],
}
VENDOR_BY_REGION = {"West": "Apex Field Tech", "Central": "NorthStar Install", "East": "FieldPro Services"}
ABORT_REASONS = ["Site not ready (no access)", "Circuit not active", "Wrong hardware shipped", "Technician no-show", "Power not available in network closet"]

def d(x): return x.isoformat() if x else ""

sites = []
first_wave = date(2026, 10, 19)
for i in range(1, 201):
    region = ["West", "Central", "East"][(i - 1) % 3]
    city, state = random.choice(CITIES[region])
    wave = (i - 1) // 14 + 1                       # 15 weekly waves of ~14 sites
    go_live = first_wave + timedelta(weeks=wave - 1)
    carrier = "Cascade Fiber" if random.random() < 0.45 else "Bluewave Telecom"
    vendor = VENDOR_BY_REGION[region]

    order = go_live - timedelta(days=45)
    due = order + timedelta(days=30)               # carrier contract: 30 days from order
    late_chance = 0.35 if carrier == "Cascade Fiber" else 0.10
    late_days = random.randint(4, 21) if random.random() < late_chance else 0
    actual = due + timedelta(days=late_days - random.randint(0, 3) if late_days == 0 else late_days)
    circuit_delivered = actual if actual <= TODAY else None
    circuit_status = "Delivered" if circuit_delivered else ("Overdue" if due < TODAY else "Ordered")

    # hardware: a router backorder hits waves 6-7
    if wave in (6, 7) and random.random() < 0.55:
        hw_status, hw_eta = "Backordered", date(2026, 12, 4)
    elif go_live - timedelta(days=10) <= TODAY:
        hw_status, hw_eta = "Delivered", go_live - timedelta(days=12)
    elif go_live - timedelta(days=20) <= TODAY:
        hw_status, hw_eta = "Shipped", go_live - timedelta(days=8)
    else:
        hw_status, hw_eta = "Not shipped", go_live - timedelta(days=10)

    site_ready = "Yes" if go_live - timedelta(days=14) <= TODAY else "Not confirmed"
    if go_live > TODAY and go_live <= TODAY + timedelta(days=21) and random.random() < 0.15:
        site_ready = "No"

    attempts, abort_reason, install_status, live_date, tech_date = 0, "", "Not started", None, None
    abort_chance = 0.22 if vendor == "NorthStar Install" else 0.07
    if go_live < TODAY:
        attempts = 1
        circuit_missing = not circuit_delivered or circuit_delivered > go_live   # no circuit on visit day
        if circuit_missing or random.random() < abort_chance:
            install_status = "Aborted"
            abort_reason = "Circuit not active" if circuit_missing else random.choice(ABORT_REASONS)
            if random.random() < 0.6 and circuit_delivered:   # rescheduled and finished
                attempts, install_status = 2, "Live"
                live_date = max(go_live + timedelta(days=random.randint(5, 12)), circuit_delivered + timedelta(days=2))
                if live_date > TODAY: install_status, live_date, tech_date = "Rescheduled", None, go_live + timedelta(days=14)
            else:
                tech_date = TODAY + timedelta(days=random.randint(3, 15))
                install_status = "Rescheduled"
        else:
            install_status, live_date = "Live", go_live
            tech_date = go_live
    elif go_live <= TODAY + timedelta(days=21):
        install_status = "Scheduled" if random.random() < 0.8 else "Not started"
        tech_date = go_live if install_status == "Scheduled" else None

    sites.append({
        "site_id": f"S{i:03d}", "name": f"{city} Store #{100 + i}", "city": city, "state": state,
        "region": region, "wave": wave, "go_live_target": d(go_live),
        "carrier": carrier, "circuit_ordered": d(order), "circuit_due": d(due),
        "circuit_delivered": d(circuit_delivered), "circuit_status": circuit_status,
        "hardware_status": hw_status, "hardware_eta": d(hw_eta),
        "site_ready": site_ready, "install_vendor": vendor, "technician_date": d(tech_date),
        "install_attempts": attempts, "install_status": install_status,
        "last_abort_reason": abort_reason, "live_date": d(live_date),
    })

with open(HERE / "sites.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(sites[0].keys()))
    w.writeheader(); w.writerows(sites)

vendors = [
    {"name": "Bluewave Telecom", "type": "Carrier", "contract": "contracts/carrier_msa.md", "account_manager": "Dana Reyes", "email": "dana.reyes@bluewave.example"},
    {"name": "Cascade Fiber", "type": "Carrier", "contract": "contracts/carrier_msa.md", "account_manager": "Victor Lin", "email": "victor.lin@cascadefiber.example"},
    {"name": "Apex Field Tech", "type": "Install vendor", "contract": "contracts/install_vendor_sow.md", "account_manager": "Maria Soto", "email": "maria.soto@apexfield.example"},
    {"name": "NorthStar Install", "type": "Install vendor", "contract": "contracts/install_vendor_sow.md", "account_manager": "Greg Patel", "email": "greg.patel@northstar.example"},
    {"name": "FieldPro Services", "type": "Install vendor", "contract": "contracts/install_vendor_sow.md", "account_manager": "Keisha Brown", "email": "keisha.brown@fieldpro.example"},
]
with open(HERE / "vendors.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(vendors[0].keys()))
    w.writeheader(); w.writerows(vendors)

# ---- vendor and site emails that mention real site IDs ----
by = lambda **kw: [s for s in sites if all(s[k] == v for k, v in kw.items())]
upcoming = [s for s in sites if TODAY < date.fromisoformat(s["go_live_target"]) <= TODAY + timedelta(days=21)]
cascade_open = [s["site_id"] for s in sites if s["carrier"] == "Cascade Fiber" and s["circuit_status"] != "Delivered"][:6]
backordered = [s["site_id"] for s in sites if s["hardware_status"] == "Backordered"]
not_ready = [s for s in upcoming if s["site_ready"] == "No"]
northstar_aborts = [s["site_id"] for s in by(install_vendor="NorthStar Install") if s["install_attempts"] >= 1 and s["last_abort_reason"]]

emails = {
"2026-11-09_cascade_delay_notice.txt": f"""From: Victor Lin <victor.lin@cascadefiber.example>
To: Rollout PMO
Date: 2026-11-09
Subject: Circuit delivery update - construction delays

Hi team,

Due to a shortage of splicing crews in several metro areas, delivery of the
following circuits will slip by an estimated 2 to 3 weeks: {', '.join(cascade_open)}.

We will send new firm order commitment (FOC) dates by end of next week.
We appreciate your patience.

Victor Lin, Account Manager, Cascade Fiber
""",
"2026-11-10_router_backorder.txt": f"""From: Supply Desk <orders@netdistro.example>
To: Rollout PMO
Date: 2026-11-10
Subject: Backorder - EdgeRouter 4400 (order PO-77812)

The EdgeRouter 4400 units on PO-77812 are backordered. Current estimated
ship date is 2026-12-04. Affected sites on this PO: {', '.join(backordered)}.

A substitute model (EdgeRouter 4300) is available now if engineering approves it.

Supply Desk, NetDistro
""",
"2026-11-12_northstar_tech_shortage.txt": f"""From: Greg Patel <greg.patel@northstar.example>
To: Rollout PMO
Date: 2026-11-12
Subject: Central region technician capacity

Hi,

Two of our Central region technicians are out through the end of the month.
We can cover about 8 installs per week instead of 12 in Central until December 1.
We are also reviewing the recent aborted visits ({', '.join(northstar_aborts[:5])}).

Greg Patel, NorthStar Install
""",
"2026-11-13_site_not_ready.txt": f"""From: Store Operations
To: Rollout PMO
Date: 2026-11-13
Subject: Stores not ready for install

FYI, these stores will not be ready on their scheduled date:
{chr(10).join(f"- {s['site_id']} {s['name']}: remodel in progress, network closet has no power yet" for s in not_ready) or "- none this week"}

Please move their installs out at least two weeks.

Store Operations
""",
"2026-11-14_bluewave_foc.txt": """From: Dana Reyes <dana.reyes@bluewave.example>
To: Rollout PMO
Date: 2026-11-14
Subject: FOC confirmations for wave 6 and 7

Hi team,

All Bluewave circuits for waves 6 and 7 are confirmed on schedule.
Firm order commitment dates have been loaded into the portal.

Dana Reyes, Bluewave Telecom
""",
"2026-11-15_leadership_ask.txt": """From: VP Operations
To: Rollout PMO
Date: 2026-11-15
Subject: Need a clear picture for Monday

Before Monday's leadership review I need: how many stores are live, what
is at risk for the next three weeks and why, and what you need from me.
Keep it to one page.
""",
}
(HERE / "emails").mkdir(exist_ok=True)
for name, body in emails.items():
    (HERE / "emails" / name).write_text(body)

print(f"Wrote {len(sites)} sites, {len(vendors)} vendors, {len(emails)} emails. Program date: {TODAY}")
