"""Reads and writes the site tracker (data/sites.csv) safely.

Used by both the AI tools (rollout_server.py) and the web GUI (gui/app.py), so the
same rules apply however a change is made:
  - every value is checked (dates, status words, vendor names) before anything is saved
  - some fields fill themselves in, for example circuit_status from the circuit dates
  - the file is rewritten in one step, so a crash never leaves it half-written
  - every change is recorded in audit/changes.jsonl with who made it, why, and the old
    and new values, so any edit can be traced and undone by hand
"""
import csv, fcntl, json, os, re, tempfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent)
DATA, AUDIT = PROJECT / "data", PROJECT / "audit"
SITES_CSV, VENDORS_CSV = DATA / "sites.csv", DATA / "vendors.csv"
CHANGES_LOG = AUDIT / "changes.jsonl"
TODAY = date.fromisoformat(os.environ.get("ROLLOUT_TODAY", "2026-11-16"))

FIELDS = ["site_id", "name", "city", "state", "region", "wave", "go_live_target", "carrier",
          "circuit_ordered", "circuit_due", "circuit_delivered", "circuit_status", "hardware_status",
          "hardware_eta", "site_ready", "install_vendor", "technician_date", "install_attempts",
          "install_status", "last_abort_reason", "live_date"]

CHOICES = {
    "region": ["West", "Central", "East"],
    "circuit_status": ["Ordered", "Delivered", "Overdue"],
    "hardware_status": ["Not shipped", "Shipped", "Delivered", "Backordered"],
    "site_ready": ["Yes", "No", "Not confirmed"],
    "install_status": ["Not started", "Scheduled", "Rescheduled", "Live"],
}
ABORT_REASONS = ["Site not ready (no access)", "Circuit not active", "Wrong hardware shipped",
                 "Technician no-show", "Power not available in network closet"]
DATE_FIELDS = ["go_live_target", "circuit_ordered", "circuit_due", "circuit_delivered",
               "hardware_eta", "technician_date", "live_date"]
INT_FIELDS = ["wave", "install_attempts"]
REQUIRED = ["site_id", "name", "city", "state", "region", "wave", "go_live_target", "carrier",
            "install_vendor"]
CIRCUIT_DAYS = 30   # carrier contract, Section 4.1


class ValidationError(ValueError):
    """A change was refused. .errors lists every problem in plain words."""
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


# ---------- reading ----------
def load_sites():
    with open(SITES_CSV, newline="") as f:
        return list(csv.DictReader(f))

def load_vendors():
    with open(VENDORS_CSV, newline="") as f:
        return list(csv.DictReader(f))

def vendor_names(kind):
    """kind: 'Carrier' or 'Install vendor'."""
    return [v["name"] for v in load_vendors() if v["type"] == kind]

def choices():
    """Every allowed value, for building dropdowns."""
    return {**CHOICES, "carrier": vendor_names("Carrier"), "install_vendor": vendor_names("Install vendor"),
            "last_abort_reason": ABORT_REASONS}

def recent_changes(limit=50, site_id=""):
    if not CHANGES_LOG.exists():
        return []
    rows = [json.loads(l) for l in CHANGES_LOG.read_text().splitlines() if l.strip()]
    if site_id:
        rows = [r for r in rows if r["site_id"].lower() == site_id.strip().lower()]
    return rows[-limit:][::-1]


# ---------- checking ----------
def _clean(value):
    return "" if value is None else str(value).strip()

def _check_row(row):
    """Return a list of problems with a full row. Empty list means it is valid."""
    errs = []
    for f in REQUIRED:
        if not row.get(f):
            errs.append(f"{f} is required")
    if row.get("site_id") and not re.fullmatch(r"S\d{3,}", row["site_id"]):
        errs.append(f"site_id '{row['site_id']}' must look like S201")
    for f in DATE_FIELDS:
        if row.get(f):
            try:
                date.fromisoformat(row[f])
            except ValueError:
                errs.append(f"{f} '{row[f]}' must be a date written YYYY-MM-DD")
    for f in INT_FIELDS:
        if row.get(f) != "" and not re.fullmatch(r"\d+", row.get(f, "")):
            errs.append(f"{f} '{row.get(f)}' must be a whole number")
    if row.get("wave", "").isdigit() and int(row["wave"]) < 1:
        errs.append("wave must be 1 or more")
    allowed = choices()
    for f in list(CHOICES) + ["carrier", "install_vendor"]:
        if row.get(f) and row[f] not in allowed[f]:
            errs.append(f"{f} '{row[f]}' is not allowed. Use one of: {', '.join(allowed[f])}")
    if row.get("state") and not re.fullmatch(r"[A-Z]{2}", row["state"]):
        errs.append(f"state '{row['state']}' must be a 2-letter code such as TX")
    # rules that tie fields together
    if row.get("install_status") == "Live" and not row.get("live_date"):
        errs.append("a Live site needs a live_date")
    if row.get("live_date") and row.get("install_status") != "Live":
        errs.append("live_date is set but install_status is not Live")
    if row.get("install_status") == "Rescheduled" and not row.get("last_abort_reason"):
        errs.append("a Rescheduled site needs a last_abort_reason")
    if row.get("hardware_status") == "Backordered" and not row.get("hardware_eta"):
        errs.append("Backordered hardware needs a hardware_eta")
    if row.get("circuit_delivered") and row.get("circuit_ordered") and not errs_in_dates(row, "circuit_ordered", "circuit_delivered"):
        if row["circuit_delivered"] < row["circuit_ordered"]:
            errs.append("circuit_delivered is before circuit_ordered")
    return errs

def errs_in_dates(row, *fields):
    try:
        for f in fields:
            date.fromisoformat(row[f])
        return False
    except ValueError:
        return True

def _derive(row, given):
    """Fill in fields that follow from others. Returns a list of what it filled in."""
    notes = []
    if row.get("circuit_ordered") and not row.get("circuit_due") and not errs_in_dates(row, "circuit_ordered"):
        row["circuit_due"] = (date.fromisoformat(row["circuit_ordered"]) + timedelta(days=CIRCUIT_DAYS)).isoformat()
        notes.append(f"circuit_due set to {row['circuit_due']} (30 days after order, carrier contract Section 4.1)")
    if "circuit_status" not in given and row.get("circuit_ordered"):
        if row.get("circuit_delivered"):
            new = "Delivered"
        elif row.get("circuit_due") and not errs_in_dates(row, "circuit_due") and date.fromisoformat(row["circuit_due"]) < TODAY:
            new = "Overdue"
        else:
            new = "Ordered"
        if row.get("circuit_status") != new:
            row["circuit_status"] = new
            notes.append(f"circuit_status set to {new} from the circuit dates")
    if row.get("live_date") and "install_status" not in given and row.get("install_status") != "Live":
        row["install_status"] = "Live"
        notes.append("install_status set to Live because live_date was given")
    if row.get("install_attempts") == "":
        row["install_attempts"] = "0"
    return notes


# ---------- writing ----------
@contextmanager
def _locked():
    """Only one writer at a time, whether it is the AI or the GUI."""
    AUDIT.mkdir(exist_ok=True)
    with open(AUDIT / ".sites.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

def _save(rows):
    fd, tmp = tempfile.mkstemp(dir=DATA, prefix=".sites-", suffix=".csv")
    with os.fdopen(fd, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)
    os.replace(tmp, SITES_CSV)

def _log(site_id, action, changes, by, reason):
    AUDIT.mkdir(exist_ok=True)
    with open(CHANGES_LOG, "a") as f:
        f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "site_id": site_id,
                            "action": action, "by": by, "reason": reason, "changes": changes}) + "\n")

def update_site(site_id, changes, by, reason=""):
    """Change some fields of one site. changes: {field: new value}. Use "" to clear a field.
    Returns the saved row, what changed, and anything filled in automatically.
    Raises ValidationError and saves nothing if any value is wrong."""
    if not isinstance(changes, dict) or not changes:
        raise ValidationError(["give at least one field to change"])
    unknown = [k for k in changes if k not in FIELDS]
    if unknown:
        raise ValidationError([f"unknown field(s): {', '.join(unknown)}. Fields are: {', '.join(FIELDS)}"])
    if "site_id" in changes and _clean(changes["site_id"]).upper() != site_id.strip().upper():
        raise ValidationError(["site_id cannot be changed"])
    with _locked():
        rows = load_sites()
        idx = next((i for i, r in enumerate(rows) if r["site_id"].lower() == site_id.strip().lower()), None)
        if idx is None:
            raise ValidationError([f"No site with ID {site_id}"])
        before = dict(rows[idx])
        row = dict(before)
        given = {k: _clean(v) for k, v in changes.items()}
        row.update(given)
        notes = _derive(row, given)
        errs = _check_row(row)
        if errs:
            raise ValidationError(errs)
        diff = {k: {"from": before.get(k, ""), "to": row[k]} for k in FIELDS if before.get(k, "") != row[k]}
        if not diff:
            return {"site_id": row["site_id"], "saved": False, "changed": {}, "auto_filled": [],
                    "note": "Nothing changed: the site already has those values.", "site": row}
        rows[idx] = row
        _save(rows)
        _log(row["site_id"], "update", diff, by, reason)
    return {"site_id": row["site_id"], "saved": True, "changed": diff, "auto_filled": notes, "site": row}

def next_site_id(rows=None):
    rows = rows if rows is not None else load_sites()
    n = max((int(r["site_id"][1:]) for r in rows if r["site_id"][1:].isdigit()), default=0) + 1
    return f"S{n:03d}"

def add_site(fields, by, reason=""):
    """Add a new site. fields: {field: value}. site_id is optional (the next free ID is used).
    Raises ValidationError and saves nothing if any value is wrong."""
    unknown = [k for k in fields if k not in FIELDS]
    if unknown:
        raise ValidationError([f"unknown field(s): {', '.join(unknown)}"])
    with _locked():
        rows = load_sites()
        given = {k: _clean(v) for k, v in fields.items()}
        row = {k: "" for k in FIELDS}
        row.update({"circuit_status": "", "hardware_status": "Not shipped", "site_ready": "Not confirmed",
                    "install_status": "Not started", "install_attempts": "0"})
        row.update({k: v for k, v in given.items() if v != ""})
        row["site_id"] = (row["site_id"] or next_site_id(rows)).upper()
        if any(r["site_id"] == row["site_id"] for r in rows):
            raise ValidationError([f"site {row['site_id']} already exists"])
        notes = _derive(row, given)
        errs = _check_row(row)
        if not row["circuit_ordered"]:
            errs.append("circuit_ordered is required (the date the circuit was ordered)")
        if errs:
            raise ValidationError(errs)
        rows.append(row)
        rows.sort(key=lambda r: int(r["site_id"][1:]))
        _save(rows)
        _log(row["site_id"], "add", {k: {"from": "", "to": v} for k, v in row.items() if v}, by, reason)
    return {"site_id": row["site_id"], "saved": True, "auto_filled": notes, "site": row}
