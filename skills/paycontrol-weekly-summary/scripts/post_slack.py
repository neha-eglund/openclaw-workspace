#!/usr/bin/env python3
"""
Post the weekly summary to Slack: 1 main message + 4 thread replies.

Reads report content from /tmp/ws_report.json (written by agent before calling this script).

Usage:
    python3 scripts/post_slack.py           # live post
    python3 scripts/post_slack.py --dry-run # print to stdout, skip Slack
"""
import json, sys, urllib.request, urllib.error, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

DRY_RUN = args.dry_run

token   = cfg.REPORTS_BOT_TOKEN
channel = cfg.SLACK_CHANNEL_ID

report         = json.loads(Path(cfg.TMP_REPORT).read_text())
main_message   = report['main_message']
thread_reply_1 = report['thread_reply_1']  # week-over-week
thread_reply_2 = report['thread_reply_2']  # stale + action items + contributors
thread_reply_3 = report['thread_reply_3']  # board flow
thread_reply_4 = report['thread_reply_4']  # PR tracking

DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if DRY_RUN:
    print("=== DRY RUN — not posting to Slack ===\n")
    print(f"[MAIN]\n{main_message}\n")
    print(f"{DIVIDER}\n[THREAD 1 — Week-over-week]\n{thread_reply_1}\n")
    print(f"{DIVIDER}\n[THREAD 2 — Stale + Action items + Contributors]\n{thread_reply_2}\n")
    print(f"{DIVIDER}\n[THREAD 3 — Board flow]\n{thread_reply_3}\n")
    print(f"{DIVIDER}\n[THREAD 4 — PR tracking]\n{thread_reply_4}\n")
    raise SystemExit(0)


def post(text, thread_ts=None):
    payload = {'channel': channel, 'text': text}
    if thread_ts:
        payload['thread_ts'] = thread_ts
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        'https://slack.com/api/chat.postMessage',
        data=data,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except urllib.error.URLError as e:
        raise Exception(f"Network error posting to Slack: {e}") from e
    if not resp.get('ok'):
        raise Exception(f"Slack error: {resp.get('error')}  (channel={channel})")
    return resp['ts']


ts = post(main_message)
print(f"Main message posted: {ts}")
post(thread_reply_1, thread_ts=ts)
post(thread_reply_2, thread_ts=ts)
post(thread_reply_3, thread_ts=ts)
post(thread_reply_4, thread_ts=ts)
print("All 4 thread replies posted.")
