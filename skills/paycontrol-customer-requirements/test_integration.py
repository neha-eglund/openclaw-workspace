"""
Integration checks for paycontrol-customer-requirements.
Verifies Slack API access and snapshot state.
Requires internet access and valid credentials in config/.

Run:
    python3 skills/paycontrol-customer-requirements/test_integration.py
"""
import json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))
from helpers import Runner, TOKENS, NAMES, SNAPSHOTS_CF


def check_slack_read(r, token):
    def slack_get(url):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    try:
        auth = slack_get("https://slack.com/api/auth.test")
        r.check("Slack: bot token valid", auth.get("ok"), auth.get("error", ""))
    except Exception as e:
        r.check("Slack: bot token valid", False, str(e))
        return

    try:
        info = slack_get("https://slack.com/api/conversations.info?channel=C0AKQRQ6QDA")
        r.check("Slack: #paycontrol-feedback readable (channels:history scope)",
                info.get("ok") and info.get("channel", {}).get("is_member"),
                info.get("error", ""))
    except Exception as e:
        r.check("Slack: #paycontrol-feedback readable", False, str(e))

    try:
        info = slack_get("https://slack.com/api/conversations.info?channel=C0ATQEBLT89")
        r.check("Slack: #paycontrol-reports accessible (bot is member)",
                info.get("ok") and info.get("channel", {}).get("is_member"),
                info.get("error", ""))
    except Exception as e:
        r.check("Slack: #paycontrol-reports accessible", False, str(e))


def main():
    r = Runner("Customer Feedback · Integration checks")

    r.check("Config: slack-tokens.json exists", TOKENS.exists())
    r.check("Config: contributor-names.json exists", NAMES.exists())

    if TOKENS.exists():
        config = json.loads(TOKENS.read_text())
        r.check("Config: bot_token present", bool(config.get("bot_token")))
        r.check("Config: reports_bot_token present", bool(config.get("reports_bot_token")))
        r.check("Config: paycontrol_reports_channel = C0ATQEBLT89",
                config.get("paycontrol_reports_channel") == "C0ATQEBLT89")
        token = config.get("bot_token", "")
        if token:
            check_slack_read(r, token)

    if NAMES.exists():
        names = json.loads(NAMES.read_text())
        expected = {"alipas", "rasmusmiddendorff", "lirre8", "ErikWallin", "bol"}
        missing = expected - set(names.keys())
        r.check("Config: all known contributors in names cache",
                not missing, f"Missing: {missing}" if missing else "")

    snaps = sorted(SNAPSHOTS_CF.glob("snapshot-*.json"))
    r.check("Snapshot: customer feedback exists (2026-05-15)",
            any("2026-05-15" in s.name for s in snaps))
    if snaps:
        latest = json.loads(snaps[-1].read_text())
        r.check("Snapshot: cumulative from 2026-03-10",
                latest.get("window_from") == "2026-03-10",
                f"Found: {latest.get('window_from')}")

    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
