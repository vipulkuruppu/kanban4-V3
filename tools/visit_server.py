#!/usr/bin/env python3
"""Serve the Kanban board and record visits.

Serves the repository root like `python3 -m http.server`, and also accepts
beacons from index.html on POST /__visit. Each beacon is appended as one JSON
line to logs/visits.jsonl with the source IP, user agent and time spent.

    python3 tools/visit_server.py                 # http://127.0.0.1:8000
    python3 tools/visit_server.py --host 0.0.0.0  # reachable on the LAN

Use --trust-proxy only behind a reverse proxy you control; otherwise the
X-Forwarded-For header can be forged by any visitor.
"""
import argparse
import json
import os
import re
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "logs", "visits.jsonl")
MAX_BODY = 2048
EVENTS = {"start", "hidden", "end"}
VISIT_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
MAX_DURATION_MS = 7 * 24 * 3600 * 1000

_log_lock = threading.Lock()


class VisitHandler(SimpleHTTPRequestHandler):
    trust_proxy = False

    def client_ip(self):
        if self.trust_proxy:
            forwarded = self.headers.get("X-Forwarded-For", "")
            first = forwarded.split(",")[0].strip()
            if first:
                return first[:64]
        return self.client_address[0]

    def do_POST(self):
        if self.path.split("?")[0] != "/__visit":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.send_error(413)
            return
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        if not isinstance(data, dict):
            self.send_error(400)
            return

        event = data.get("event")
        visit_id = data.get("visitId")
        duration = data.get("durationMs", 0)
        if (
            event not in EVENTS
            or not isinstance(visit_id, str)
            or not VISIT_ID_RE.match(visit_id)
            or not isinstance(duration, (int, float))
            or not 0 <= duration <= MAX_DURATION_MS
        ):
            self.send_error(400)
            return

        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ip": self.client_ip(),
            "visit_id": visit_id,
            "event": event,
            "duration_ms": int(duration),
            "path": str(data.get("path", "/"))[:200],
            "user_agent": self.headers.get("User-Agent", "")[:300],
        }
        with _log_lock:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        # Keep visit logs, reports and repo internals off the web.
        top = self.path.lstrip("/").split("/")[0].split("?")[0]
        if top in {"logs", "visit-reports", "security-reports", ".git", ".claude", "tools"}:
            self.send_error(404)
            return
        super().do_GET()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--trust-proxy", action="store_true",
                        help="take the client IP from X-Forwarded-For")
    args = parser.parse_args()

    VisitHandler.trust_proxy = args.trust_proxy
    handler = partial(VisitHandler, directory=ROOT)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {ROOT} on http://{args.host}:{args.port} (visits -> {LOG_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
