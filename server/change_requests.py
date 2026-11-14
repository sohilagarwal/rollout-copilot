"""Change requests: the AI proposes, a person decides.

Some fields are commitments to the business, not status updates: a go-live date, the install
vendor, the carrier. Moving them affects stores, crews and leadership plans, so the AI may
not change them directly. It files a change request instead, and nothing in the tracker
changes until a person approves it.

  propose()  check a change without saving it, and file it as a pending request
  decide()   approve (apply the change) or reject a pending request; done by a person
  list_requests()

Requests are kept in data/change_requests.json. Approved changes are applied through
site_store, so they are checked again and logged in audit/changes.jsonl like any other edit.
"""
import json, os, tempfile
from datetime import datetime

import site_store as st

REQUESTS = st.DATA / "change_requests.json"
PROTECTED = ["go_live_target", "install_vendor", "carrier"]   # need a person's approval


def _load():
    return json.loads(REQUESTS.read_text()) if REQUESTS.exists() else []

def _save(reqs):
    fd, tmp = tempfile.mkstemp(dir=st.DATA, prefix=".cr-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(reqs, f, indent=1)
    os.replace(tmp, REQUESTS)

def _now():
    return datetime.now().isoformat(timespec="seconds")

def dry_run(site_id, changes):
    """Check a change without saving it. Returns (diff, auto_filled). Raises ValidationError."""
    if not isinstance(changes, dict) or not changes:
        raise st.ValidationError(["give at least one field to change"])
    unknown = [k for k in changes if k not in st.FIELDS]
    if unknown:
        raise st.ValidationError([f"unknown field(s): {', '.join(unknown)}"])
    rows = st.load_sites()
    before = next((r for r in rows if r["site_id"].lower() == site_id.strip().lower()), None)
    if before is None:
        raise st.ValidationError([f"No site with ID {site_id}"])
    row, given = dict(before), {k: st._clean(v) for k, v in changes.items()}
    row.update(given)
    notes = st._derive(row, given)
    errs = st._check_row(row)
    if errs:
        raise st.ValidationError(errs)
    diff = {k: {"from": before.get(k, ""), "to": row[k]} for k in st.FIELDS if before.get(k, "") != row[k]}
    if not diff:
        raise st.ValidationError(["nothing would change: the site already has those values"])
    return before["site_id"], diff, notes

def propose(site_id, changes, reason, impact="", by="Claude"):
    """File a change request. Nothing in the tracker changes."""
    if not reason.strip():
        raise st.ValidationError(["give a reason for the change"])
    sid, diff, notes = dry_run(site_id, changes)
    with st._locked():
        reqs = _load()
        dup = next((r for r in reqs if r["status"] == "pending" and r["site_id"] == sid and r["changes"] == changes), None)
        if dup:
            return {**dup, "note": f"{dup['id']} already asks for this change and is waiting for approval."}
        req = {"id": f"CR-{len(reqs) + 1:03d}", "site_id": sid, "status": "pending", "changes": changes,
               "diff": diff, "auto_filled": notes, "reason": reason.strip(), "impact": impact.strip(),
               "proposed_by": by, "proposed_at": _now(), "decided_by": "", "decided_at": "", "decision_note": ""}
        reqs.append(req)
        _save(reqs)
    return {**req, "note": "Filed. Nothing has changed yet: a person must approve this request."}

def list_requests(status=""):
    reqs = _load()
    if status:
        reqs = [r for r in reqs if r["status"] == status.lower()]
    return reqs[::-1]

def decide(req_id, approve, by, note=""):
    """Approve (apply) or reject a pending request. Call only on a person's decision."""
    if not by.strip():
        raise st.ValidationError(["say who is deciding"])
    with st._locked():
        reqs = _load()
        req = next((r for r in reqs if r["id"].lower() == req_id.strip().lower()), None)
        if req is None:
            raise st.ValidationError([f"No change request {req_id}"])
        if req["status"] != "pending":
            raise st.ValidationError([f"{req['id']} was already {req['status']} by {req['decided_by']} on {req['decided_at']}"])
    result = None
    if approve:
        try:   # checked again: the site may have changed since the request was filed
            result = st.update_site(req["site_id"], req["changes"], by=f"{by} (approved {req['id']})",
                                    reason=f"{req['id']}: {req['reason']}")
            status = "approved"
        except st.ValidationError as e:
            status, note = "failed", "Could not apply: " + "; ".join(e.errors)
    else:
        status = "rejected"
    with st._locked():
        reqs = _load()
        req = next(r for r in reqs if r["id"] == req["id"])
        req.update({"status": status, "decided_by": by.strip(), "decided_at": _now(), "decision_note": note.strip()})
        _save(reqs)
    return {**req, "applied": result["changed"] if result else {}}
