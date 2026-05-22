#!/usr/bin/env python3
"""
Load last week's snapshot, save this week's, and print week-over-week deltas.

Expects the agent to pass current stats as environment variables or via /tmp/ws_stats.json.

Usage:
    python3 scripts/snapshot.py
    # Reads /tmp/ws_stats.json (written by agent after computing impact signals)
    # Writes /tmp/ws_deltas.json for the agent to use in the report
"""
import json, os, glob
from datetime import datetime, timezone

OUT_DIR = os.path.expanduser("~/.openclaw/workspace/nightly-results/weekly-summary")
os.makedirs(OUT_DIR, exist_ok=True)

window = json.load(open('/tmp/ws_window.json'))
TODAY = window['today']

# Load this run's stats (agent writes these after step 4)
stats = json.load(open('/tmp/ws_stats.json'))

# Load previous snapshot
snapshots = sorted(glob.glob(f"{OUT_DIR}/snapshot-*.json"))
last = json.load(open(snapshots[-1])) if snapshots else None

# Save this week's snapshot
this_snapshot = {"date": TODAY, "window_from": window['since_date'], "window_to": TODAY, **stats}
with open(f"{OUT_DIR}/snapshot-{TODAY}.json", "w") as f:
    json.dump(this_snapshot, f, indent=2)
print(f"Snapshot saved: snapshot-{TODAY}.json")

# Compute deltas
def delta(key, section, good_direction="down"):
    new_val = stats.get(section, {}).get(key, 0)
    old_val = (last or {}).get(section, {}).get(key, 0) if last else None
    if old_val is None:
        return new_val, "(no prior data)"
    d = new_val - old_val
    if d == 0:
        return new_val, "no change"
    sign = "+" if d > 0 else ""
    arrow = "↑" if d > 0 else "↓"
    is_bad = (good_direction == "down" and d > 0) or (good_direction == "up" and d < 0)
    flag = "🔴" if is_bad else "✅"
    return new_val, f"{flag} {sign}{d} {arrow}"

deltas = {}
for section in ["paycontrol", "pci", "gitops"]:
    deltas[section] = {
        "open_issues":   delta("open_issues",   section, "down"),
        "merged_prs":    delta("merged_prs",    section, "up"),
        "sec_open":      delta("sec_open",       section, "down"),
        "stale_issues":  delta("stale_issues",  section, "down"),
        "untracked_prs": delta("untracked_prs", section, "down"),
    }

json.dump({"last_date": (last or {}).get("date"), "deltas": deltas}, open('/tmp/ws_deltas.json', 'w'), indent=2)
print("Deltas written to /tmp/ws_deltas.json")
if last:
    print(f"Comparing against snapshot: {last['date']}")
else:
    print("No prior snapshot — deltas will show '(no prior data)'")
