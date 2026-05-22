#!/usr/bin/env python3
"""
Load last week's snapshot, save this week's, and print week-over-week deltas.

Reads /tmp/ws_stats.json (written by agent after computing impact signals).
Writes /tmp/ws_deltas.json for the agent to use in the report.

Usage:
    python3 scripts/snapshot.py
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

window = json.loads(Path(cfg.TMP_WINDOW).read_text())
TODAY  = window['today']
stats  = json.loads(Path(cfg.TMP_STATS).read_text())

# Load previous snapshot — exclude today's file to avoid same-day re-run returning all-zero deltas
snapshots = sorted(
    p for p in cfg.SNAPSHOT_DIR.glob("snapshot-*.json")
    if p.stem != f"snapshot-{TODAY}"
)
last = json.loads(snapshots[-1].read_text()) if snapshots else None

# Save this week's snapshot
this_snapshot = {"date": TODAY, "window_from": window['since_date'], "window_to": TODAY, **stats}
(cfg.SNAPSHOT_DIR / f"snapshot-{TODAY}.json").write_text(json.dumps(this_snapshot, indent=2))
print(f"Snapshot saved: snapshot-{TODAY}.json")


def delta(key, section, good_direction="down"):
    new_val = stats.get(section, {}).get(key, 0)
    old_val = last.get(section, {}).get(key) if last else None
    if old_val is None:
        return new_val, "(no prior data)"
    d = new_val - old_val
    if d == 0:
        return new_val, "no change"
    sign  = "+" if d > 0 else ""
    arrow = "↑" if d > 0 else "↓"
    is_bad = (good_direction == "down" and d > 0) or (good_direction == "up" and d < 0)
    flag = "🔴" if is_bad else "✅"
    return new_val, f"{flag} {sign}{d} {arrow}"


METRICS = [
    ("open_issues",   "down"),
    ("merged_prs",    "up"),
    ("sec_open",      "down"),
    ("stale_issues",  "down"),
    ("untracked_prs", "down"),
]

deltas = {
    section: {key: delta(key, section, direction) for key, direction in METRICS}
    for section in ["paycontrol", "pci", "gitops"]
}

Path(cfg.TMP_DELTAS).write_text(
    json.dumps({"last_date": (last or {}).get("date"), "deltas": deltas}, indent=2)
)
print("Deltas written to /tmp/ws_deltas.json")
print(f"Comparing against snapshot: {last['date']}" if last else "No prior snapshot — deltas will show '(no prior data)'")
