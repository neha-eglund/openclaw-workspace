#!/usr/bin/env python3
"""
Save this run's cumulative snapshot and update last-run.json.

Reads:
    /tmp/cf_feedback_items.json  — FEEDBACK_ITEMS list written by agent
    /tmp/cf_window.json          — since_date, today

Outputs:
    snapshots/snapshot-{today}.json  — cumulative snapshot
    last-run.json                    — updated with current ts

Usage:
    python3 scripts/save_snapshot.py
"""
import json, os, glob, time
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

SNAPSHOT_DIR = str(cfg.SNAPSHOT_DIR)
LAST_RUN_PATH = cfg.LAST_RUN_FILE

window = json.load(open(cfg.TMP_WINDOW))
today = window['today']
since_date = window['since_date']

items = json.load(open(cfg.TMP_ITEMS))

# Load previous cumulative snapshot
prev_snapshots = sorted(glob.glob(f"{SNAPSHOT_DIR}/snapshot-*.json"))
prev = json.load(open(prev_snapshots[-1])) if prev_snapshots else {}

# Count this run's items
new_resolved = new_tracked = new_untracked = 0
new_by_severity = {"🔴 Blocking": 0, "🟡 High": 0, "🔵 Normal": 0}
new_by_category = {}

for item in items:
    sev = item.get("severity", "")
    if sev in new_by_severity:
        new_by_severity[sev] += 1
    cat = item.get("category", "Other")
    new_by_category[cat] = new_by_category.get(cat, 0) + 1
    status = item.get("status", "")
    if status.startswith("✅"):
        new_resolved += 1
    elif status.startswith("🔧"):
        new_tracked += 1
    else:
        new_untracked += 1

# Merge with cumulative totals
cum_by_category = dict(prev.get("by_category", {}))
for cat, count in new_by_category.items():
    cum_by_category[cat] = cum_by_category.get(cat, 0) + count

this_snapshot = {
    "date":         today,
    "window_from":  prev.get("window_from", "2026-03-10"),
    "window_to":    today,
    "total":        prev.get("total", 0)    + len(items),
    "resolved":     prev.get("resolved", 0) + new_resolved,
    "tracked":      prev.get("tracked", 0)  + new_tracked,
    "untracked":    prev.get("untracked", 0) + new_untracked,
    "blocking":     prev.get("blocking", 0) + new_by_severity.get("🔴 Blocking", 0),
    "high":         prev.get("high", 0)     + new_by_severity.get("🟡 High", 0),
    "normal":       prev.get("normal", 0)   + new_by_severity.get("🔵 Normal", 0),
    "by_category":  cum_by_category,
}

with open(f"{SNAPSHOT_DIR}/snapshot-{today}.json", "w") as f:
    json.dump(this_snapshot, f, indent=2)
print(f"Snapshot saved: snapshot-{today}.json")

# Compute week-over-week deltas for the report
def fmt_delta(new_val, old_val, good_direction="down"):
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
for key, direction in [("total","up"), ("resolved","up"), ("tracked","up"),
                        ("untracked","down"), ("blocking","down"), ("high","down")]:
    deltas[key] = fmt_delta(this_snapshot[key], prev.get(key), direction)

json.dump({"prev_date": prev.get("date"), "deltas": deltas, "snapshot": this_snapshot},
          open(cfg.TMP_DELTAS, 'w'), indent=2)

# Update last-run.json
json.dump({
    "last_ts":    str(time.time()),
    "last_date":  today,
    "window_from": since_date,
    "window_to":  today,
    "items_found": len(items),
}, open(LAST_RUN_PATH, 'w'), indent=2)

print(f"last-run.json updated  |  window: {since_date} -> {today}")
print("save_snapshot.py done.")
