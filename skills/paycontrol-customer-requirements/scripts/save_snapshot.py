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
import json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

RESOLVED_PREFIX   = "✅"
TRACKED_PREFIX    = "🔧"
SEVERITY_BLOCKING = "🔴 Blocking"
SEVERITY_HIGH     = "🟡 High"
SEVERITY_NORMAL   = "🔵 Normal"

window     = json.loads(Path(cfg.TMP_WINDOW).read_text())
today      = window['today']
since_date = window['since_date']
items      = json.loads(Path(cfg.TMP_ITEMS).read_text())

# Load previous cumulative snapshot — exclude today's file to avoid double-counting on re-runs
prev_snapshots = sorted(
    p for p in cfg.SNAPSHOT_DIR.glob("snapshot-*.json")
    if p.stem != f"snapshot-{today}"
)
prev = json.loads(prev_snapshots[-1].read_text()) if prev_snapshots else {}

# Count this run's items
new_resolved = new_tracked = new_untracked = 0
new_by_severity = {SEVERITY_BLOCKING: 0, SEVERITY_HIGH: 0, SEVERITY_NORMAL: 0}
new_by_category = {}

for item in items:
    sev = item.get("severity", "")
    if sev in new_by_severity:
        new_by_severity[sev] += 1
    cat = item.get("category", "Other")
    new_by_category[cat] = new_by_category.get(cat, 0) + 1
    status = item.get("status", "")
    if status.startswith(RESOLVED_PREFIX):
        new_resolved += 1
    elif status.startswith(TRACKED_PREFIX):
        new_tracked += 1
    else:
        new_untracked += 1

# Merge category counts with cumulative totals
cum_by_category = {**prev.get("by_category", {})}
for cat, count in new_by_category.items():
    cum_by_category[cat] = cum_by_category.get(cat, 0) + count

this_snapshot = {
    "date":        today,
    "window_from": prev.get("window_from", since_date),
    "window_to":   today,
    "total":       prev.get("total",     0) + len(items),
    "resolved":    prev.get("resolved",  0) + new_resolved,
    "tracked":     prev.get("tracked",   0) + new_tracked,
    "untracked":   prev.get("untracked", 0) + new_untracked,
    "blocking":    prev.get("blocking",  0) + new_by_severity[SEVERITY_BLOCKING],
    "high":        prev.get("high",      0) + new_by_severity[SEVERITY_HIGH],
    "normal":      prev.get("normal",    0) + new_by_severity[SEVERITY_NORMAL],
    "by_category": cum_by_category,
}

(cfg.SNAPSHOT_DIR / f"snapshot-{today}.json").write_text(json.dumps(this_snapshot, indent=2))
print(f"Snapshot saved: snapshot-{today}.json")


def fmt_delta(new_val, old_val, good_direction="down"):
    if old_val is None:
        return "(no prior data)"
    d = new_val - old_val
    if d == 0:
        return "no change"
    sign  = "+" if d > 0 else ""
    arrow = "↑" if d > 0 else "↓"
    is_bad = (good_direction == "down" and d > 0) or (good_direction == "up" and d < 0)
    flag = "🔴" if is_bad else "✅"
    return f"{flag} {sign}{d} {arrow}"


deltas = {
    key: fmt_delta(this_snapshot[key], prev.get(key), direction)
    for key, direction in [
        ("total",     "up"),
        ("resolved",  "up"),
        ("tracked",   "up"),
        ("untracked", "down"),
        ("blocking",  "down"),
        ("high",      "down"),
    ]
}

Path(cfg.TMP_DELTAS).write_text(
    json.dumps({"prev_date": prev.get("date"), "deltas": deltas, "snapshot": this_snapshot}, indent=2)
)

cfg.LAST_RUN_FILE.write_text(json.dumps({
    "last_ts":     str(time.time()),
    "last_date":   today,
    "window_from": since_date,
    "window_to":   today,
    "items_found": len(items),
}, indent=2))

print(f"last-run.json updated  |  window: {since_date} -> {today}")
print("save_snapshot.py done.")
