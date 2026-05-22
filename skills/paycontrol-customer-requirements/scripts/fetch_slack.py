#!/usr/bin/env python3
"""
Fetch Slack messages, reactions, and thread replies from #paycontrol-feedback.

Outputs:
    /tmp/cf_messages.json       — list of messages since last run
    /tmp/cf_threads.json        — dict of ts -> list of thread replies
    /tmp/cf_reaction_resolved.json   — list of ts with ✅ reaction
    /tmp/cf_reaction_acknowledged.json — list of ts with 👍 reaction
    /tmp/cf_window.json         — {"since_date": "...", "today": "..."}

Usage:
    export SLACK_TOKEN=...
    python3 scripts/fetch_slack.py
"""
import json, os, subprocess, sys
from datetime import datetime, timezone

CHANNEL_ID = "C0AKQRQ6QDA"
LAST_RUN_PATH = os.path.expanduser(
    "~/.openclaw/workspace/nightly-results/customer-feedback/last-run.json"
)

token = os.environ.get("SLACK_TOKEN")
if not token:
    cfg = json.load(open(os.path.expanduser("~/.openclaw/workspace/config/slack-tokens.json")))
    token = cfg["bot_token"]

# Determine oldest timestamp to fetch from
oldest = "0"
if os.path.exists(LAST_RUN_PATH):
    d = json.load(open(LAST_RUN_PATH))
    oldest = d.get("last_ts", "0")
print(f"Fetching since ts={oldest}")


def slack_get(url, params=""):
    result = subprocess.run(
        ["curl", "-s", url + params,
         "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)


# Fetch messages
resp = slack_get(
    "https://slack.com/api/conversations.history",
    f"?channel={CHANNEL_ID}&oldest={oldest}&limit=200"
)
messages = resp.get("messages", [])
json.dump(messages, open('/tmp/cf_messages.json', 'w'), indent=2)
print(f"Messages fetched: {len(messages)}")

# Derive window dates
today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
since_date = today
if messages:
    oldest_ts = min(float(m['ts']) for m in messages)
    since_date = datetime.utcfromtimestamp(oldest_ts).strftime('%Y-%m-%d')
json.dump({"since_date": since_date, "today": today}, open('/tmp/cf_window.json', 'w'))
print(f"Window: {since_date} -> {today}")

# Classify reactions
resolved_ts = []
acknowledged_ts = []
for m in messages:
    for r in m.get("reactions", []):
        if r["name"] in ("white_check_mark", "heavy_check_mark"):
            resolved_ts.append(m["ts"])
        elif r["name"] in ("+1", "thumbsup"):
            acknowledged_ts.append(m["ts"])
json.dump(resolved_ts, open('/tmp/cf_reaction_resolved.json', 'w'))
json.dump(acknowledged_ts, open('/tmp/cf_reaction_acknowledged.json', 'w'))
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
        replies = resp.get("messages", [])
        threads[ts] = replies[1:]  # skip parent
json.dump(threads, open('/tmp/cf_threads.json', 'w'), indent=2)
print(f"Threads fetched: {len(threads)}")

print("fetch_slack.py done.")
