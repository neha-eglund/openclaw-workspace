#!/usr/bin/env python3
"""
Fetch Slack messages, reactions, and thread replies from #paycontrol-feedback.

Outputs:
    /tmp/cf_messages.json             — list of messages since last run
    /tmp/cf_threads.json              — dict of ts -> list of thread replies
    /tmp/cf_reaction_resolved.json    — list of ts with ✅ reaction
    /tmp/cf_reaction_acknowledged.json — list of ts with 👍 reaction
    /tmp/cf_window.json               — {"since_date": "...", "today": "..."}

Usage:
    export SLACK_TOKEN=...
    python3 scripts/fetch_slack.py
"""
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

token = cfg.SLACK_TOKEN
CHANNEL_ID = cfg.SLACK_CHANNEL_ID

RESOLVED_REACTIONS    = {"white_check_mark", "heavy_check_mark"}
ACKNOWLEDGED_REACTIONS = {"+1", "thumbsup"}

# Determine oldest timestamp to fetch from
oldest = "0"
if cfg.LAST_RUN_FILE.exists():
    oldest = json.loads(cfg.LAST_RUN_FILE.read_text()).get("last_ts", "0")
print(f"Fetching since ts={oldest}")


def slack_get(url, params=""):
    result = subprocess.run(
        ["curl", "-s", url + params, "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Warning: failed to parse Slack response: {e}", file=sys.stderr)
        return {}


# Fetch messages
resp = slack_get(
    "https://slack.com/api/conversations.history",
    f"?channel={CHANNEL_ID}&oldest={oldest}&limit=200"
)
messages = resp.get("messages", [])
Path(cfg.TMP_MESSAGES).write_text(json.dumps(messages, indent=2))
print(f"Messages fetched: {len(messages)}")

# Derive window dates
today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
if messages:
    oldest_ts = min(float(m['ts']) for m in messages)
    since_date = datetime.utcfromtimestamp(oldest_ts).strftime('%Y-%m-%d')
else:
    since_date = today
Path(cfg.TMP_WINDOW).write_text(json.dumps({"since_date": since_date, "today": today}))
print(f"Window: {since_date} -> {today}")

# Classify reactions
resolved_ts = []
acknowledged_ts = []
for m in messages:
    for r in m.get("reactions", []):
        if r["name"] in RESOLVED_REACTIONS:
            resolved_ts.append(m["ts"])
        elif r["name"] in ACKNOWLEDGED_REACTIONS:
            acknowledged_ts.append(m["ts"])
Path(cfg.TMP_RESOLVED).write_text(json.dumps(resolved_ts))
Path(cfg.TMP_ACKNOWLEDGED).write_text(json.dumps(acknowledged_ts))
print(f"Reactions — resolved: {len(resolved_ts)}  acknowledged: {len(acknowledged_ts)}")

# Fetch threads for messages that have replies
threads = {}
for m in messages:
    if m.get("reply_count", 0) > 0:
        ts = m["ts"]
        resp = slack_get(
            "https://slack.com/api/conversations.replies",
            f"?channel={CHANNEL_ID}&ts={ts}"
        )
        threads[ts] = resp.get("messages", [])[1:]  # skip parent
Path(cfg.TMP_THREADS).write_text(json.dumps(threads, indent=2))
print(f"Threads fetched: {len(threads)}")

print("fetch_slack.py done.")
