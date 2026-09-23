#!/usr/bin/env python3
"""Build an HTML visit report from logs/visits.jsonl.

    python3 tools/visit_report.py              # all visits
    python3 tools/visit_report.py --since 2026-09-23

Writes visit-reports/visit-report-<UTC timestamp>.html and copies it to
visit-reports/latest.html. Prints a JSON summary to stdout.
IPs and user agents come from visitors, so every value is HTML-escaped.
"""
import argparse
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "logs", "visits.jsonl")
OUT_DIR = os.path.join(ROOT, "visit-reports")


def fmt_duration(ms):
    s = round(ms / 1000)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def load_visits(since):
    visits = defaultdict(lambda: {"events": 0, "duration_ms": 0, "ended": False})
    bad_lines = 0
    if not os.path.exists(LOG_PATH):
        return [], bad_lines
    with open(LOG_PATH, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
                ts, vid = r["ts"], r["visit_id"]
            except (ValueError, KeyError, TypeError):
                bad_lines += 1
                continue
            if since and ts[:10] < since:
                continue
            v = visits[vid]
            v["visit_id"] = vid
            v.setdefault("ip", r.get("ip", ""))
            v.setdefault("user_agent", r.get("user_agent", ""))
            v.setdefault("path", r.get("path", "/"))
            v["first_seen"] = min(v.get("first_seen", ts), ts)
            v["last_seen"] = max(v.get("last_seen", ts), ts)
            v["events"] += 1
            # Beacons carry cumulative visible time, so the largest one wins.
            v["duration_ms"] = max(v["duration_ms"], int(r.get("duration_ms", 0)))
            v["ended"] = v["ended"] or r.get("event") == "end"
    return sorted(visits.values(), key=lambda v: v["first_seen"], reverse=True), bad_lines


def build_html(visits, generated_at, since):
    by_ip = defaultdict(lambda: {"visits": 0, "duration_ms": 0, "last_seen": ""})
    for v in visits:
        s = by_ip[v["ip"]]
        s["visits"] += 1
        s["duration_ms"] += v["duration_ms"]
        s["last_seen"] = max(s["last_seen"], v["last_seen"])
    total_ms = sum(v["duration_ms"] for v in visits)
    avg_ms = total_ms / len(visits) if visits else 0

    visit_rows = "\n".join(
        "<tr>"
        f"<td>{escape(v['first_seen'])}</td>"
        f"<td class=mono>{escape(v['ip'])}</td>"
        f"<td class=num>{fmt_duration(v['duration_ms'])}</td>"
        f"<td>{'Closed' if v['ended'] else 'Open / unknown'}</td>"
        f"<td>{escape(v['path'])}</td>"
        f"<td class=ua>{escape(v['user_agent'])}</td>"
        f"<td class=mono>{escape(v['visit_id'][:8])}</td>"
        "</tr>"
        for v in visits
    ) or '<tr><td colspan="7">No visits recorded.</td></tr>'

    ip_rows = "\n".join(
        f"<tr><td class=mono>{escape(ip)}</td><td class=num>{s['visits']}</td>"
        f"<td class=num>{fmt_duration(s['duration_ms'])}</td><td>{escape(s['last_seen'])}</td></tr>"
        for ip, s in sorted(by_ip.items(), key=lambda kv: kv[1]["visits"], reverse=True)
    ) or '<tr><td colspan="4">No visits recorded.</td></tr>'

    scope = f"since {escape(since)}" if since else "all recorded visits"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Board Visit Report</title>
<style>
:root {{ --bg:#f6f8f7; --fg:#10231b; --muted:#56675f; --line:#d5dfda; --card:#fff; --accent:#0c3324; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0f1714; --fg:#e4ece8; --muted:#9aaba3; --line:#2a3833; --card:#16211d; --accent:#8fd1b0; }}
}}
body {{ margin:0; padding:24px 16px; background:var(--bg); color:var(--fg);
  font:14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:1100px; margin:0 auto; }}
h1 {{ margin:0 0 4px; font-size:22px; color:var(--accent); }}
h2 {{ margin:28px 0 8px; font-size:16px; }}
.meta {{ color:var(--muted); margin:0 0 20px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:12px; }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 14px; }}
.tile b {{ display:block; font-size:22px; }}
.tile span {{ color:var(--muted); font-size:12px; }}
.wrap {{ overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:8px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.mono {{ font-family:ui-monospace, Menlo, monospace; white-space:nowrap; }}
.ua {{ color:var(--muted); font-size:12px; min-width:220px; }}
.note {{ color:var(--muted); font-size:12px; margin-top:20px; }}
</style>
</head>
<body>
<main>
<h1>Board Visit Report</h1>
<p class="meta">Generated {escape(generated_at)} UTC · {scope}</p>
<div class="tiles">
  <div class="tile"><b>{len(visits)}</b><span>Visits</span></div>
  <div class="tile"><b>{len(by_ip)}</b><span>Unique source IPs</span></div>
  <div class="tile"><b>{fmt_duration(total_ms)}</b><span>Total time on site</span></div>
  <div class="tile"><b>{fmt_duration(avg_ms)}</b><span>Average per visit</span></div>
</div>
<h2>By source IP</h2>
<div class="wrap"><table>
<thead><tr><th>Source IP</th><th class="num">Visits</th><th class="num">Time on site</th><th>Last seen (UTC)</th></tr></thead>
<tbody>
{ip_rows}
</tbody></table></div>
<h2>Visits</h2>
<div class="wrap"><table>
<thead><tr><th>Started (UTC)</th><th>Source IP</th><th class="num">Time on site</th><th>Session</th><th>Path</th><th>User agent</th><th>Visit</th></tr></thead>
<tbody>
{visit_rows}
</tbody></table></div>
<p class="note">Time on site counts only while the tab is visible. "Open / unknown" means no closing beacon arrived, so the time shown is the last reported value. Source IPs are personal data: keep this report internal.</p>
</main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", help="only visits on or after YYYY-MM-DD (UTC)")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    visits, bad_lines = load_visits(args.since)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"visit-report-{now.strftime('%Y%m%dT%H%M%SZ')}.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(build_html(visits, generated_at, args.since))
    shutil.copyfile(out_path, os.path.join(OUT_DIR, "latest.html"))

    print(json.dumps({
        "generated_at": now.isoformat(timespec="seconds"),
        "log_found": os.path.exists(LOG_PATH),
        "visits": len(visits),
        "unique_ips": len({v["ip"] for v in visits}),
        "total_duration_ms": sum(v["duration_ms"] for v in visits),
        "open_visits": sum(1 for v in visits if not v["ended"]),
        "malformed_log_lines": bad_lines,
        "top_ips": [
            {"ip": ip, "visits": n}
            for ip, n in sorted(
                ((ip, sum(1 for v in visits if v["ip"] == ip)) for ip in {v["ip"] for v in visits}),
                key=lambda kv: kv[1], reverse=True)[:5]
        ],
        "report": os.path.relpath(out_path, ROOT),
        "latest": os.path.relpath(os.path.join(OUT_DIR, "latest.html"), ROOT),
    }, indent=2))


if __name__ == "__main__":
    main()
