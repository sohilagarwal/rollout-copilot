"""Rollout Copilot web GUI: see the program and edit the site tracker in a browser.

Start it:   bash gui/start.sh          then open http://localhost:8000
            (or: .venv/bin/python gui/app.py --port 8000)

It uses the same numbers and readiness rules as the AI tools (rollout_server.py) and the
same checked, logged writes (site_store.py), so the GUI and Claude always agree.
Edits made here are recorded in audit/changes.jsonl as made by "GUI". The Approvals tab is where
a person approves or rejects the change requests Claude files.
Only Python's standard library is used, plus the project's own server code.
"""
import argparse, json, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "server"))
import rollout_server as rs   # noqa: E402
import site_store             # noqa: E402
import change_requests        # noqa: E402

def _raw(fn):
    """Call a tool without writing it to the AI audit log: GUI reads are not AI tool calls."""
    return getattr(fn, "__wrapped__", fn)

def all_sites():
    rows = site_store.load_sites()
    risky = {s["site_id"]: s for s in _raw(rs.at_risk_sites)(10_000)["sites"]}
    for r in rows:
        r["risk_causes"] = risky.get(r["site_id"], {}).get("causes", [])
        r["readiness_problems"] = risky.get(r["site_id"], {}).get("reasons", [])
    return rows

def api_get(path, q):
    if path == "/api/summary":
        return _raw(rs.program_summary)()
    if path == "/api/sites":
        return {"as_of": site_store.TODAY.isoformat(), "sites": all_sites()}
    if path == "/api/at_risk":
        return _raw(rs.at_risk_sites)(int(q.get("days", ["21"])[0]))
    if path == "/api/scorecard":
        return _raw(rs.vendor_scorecard)()
    if path == "/api/late_circuits":
        return _raw(rs.late_circuits)()
    if path == "/api/changes":
        return {"changes": site_store.recent_changes(int(q.get("limit", ["100"])[0]), q.get("site", [""])[0])}
    if path == "/api/requests":
        return {"requests": change_requests.list_requests(q.get("status", [""])[0])}
    if path == "/api/risk":
        return _raw(rs.risk_forecast)(int(q.get("days", ["21"])[0]), 200)
    if path == "/api/choices":
        return {"choices": site_store.choices(), "fields": site_store.FIELDS,
                "next_site_id": site_store.next_site_id(), "as_of": site_store.TODAY.isoformat()}
    return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        try:
            body = api_get(u.path, parse_qs(u.query))
        except Exception as e:  # show the problem in the page instead of a blank screen
            return self._send(500, {"error": str(e)})
        return self._send(200, body) if body is not None else self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"saved": False, "errors": ["request was not valid JSON"]})
        reason = str(payload.get("reason", "")).strip()
        try:
            if u.path == "/api/sites":
                return self._send(200, site_store.add_site(payload.get("fields", {}), by="GUI", reason=reason))
            if u.path.startswith("/api/requests/"):   # /api/requests/CR-001/approve or /reject
                _, _, _, req_id, action = u.path.split("/")
                if action not in ("approve", "reject"):
                    return self._send(404, {"error": "not found"})
                return self._send(200, change_requests.decide(req_id, action == "approve",
                                                              by=str(payload.get("by", "")).strip() and f"{payload['by'].strip()} via GUI",
                                                              note=str(payload.get("note", ""))))
            if u.path.startswith("/api/sites/"):
                site_id = u.path.rsplit("/", 1)[-1]
                return self._send(200, site_store.update_site(site_id, payload.get("changes", {}), by="GUI", reason=reason))
        except site_store.ValidationError as e:
            return self._send(400, {"saved": False, "errors": e.errors})
        return self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # keep the terminal quiet except for edits
        if self.command == "POST":
            sys.stderr.write(f"{self.address_string()} {fmt % args}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Rollout Copilot web GUI")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to allow other machines (no login!)")
    a = p.parse_args()
    print(f"Rollout Copilot GUI on http://{a.host}:{a.port}  (program date {site_store.TODAY})", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
