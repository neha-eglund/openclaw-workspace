"""
Integration checks for paycontrol-weekly-summary.
Verifies GitHub API access and snapshot state.
Requires internet access and valid credentials in config/.

Run:
    python3 skills/paycontrol-weekly-summary/test_integration.py
"""
import json, subprocess, sys, urllib.request
from pathlib import Path

from helpers import Runner, TOKENS, NAMES, SNAPSHOTS_WS, get_gh_token


def check_slack_post(r, token):
    def slack_get(url):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    try:
        auth = slack_get("https://slack.com/api/auth.test")
        r.check("Slack: reports_bot_token valid", auth.get("ok"), auth.get("error", ""))
    except Exception as e:
        r.check("Slack: reports_bot_token valid", False, str(e))
        return

    try:
        info = slack_get("https://slack.com/api/conversations.info?channel=C0ATQEBLT89")
        r.check("Slack: #paycontrol-reports accessible (bot is member)",
                info.get("ok") and info.get("channel", {}).get("is_member"),
                info.get("error", ""))
    except Exception as e:
        r.check("Slack: #paycontrol-reports accessible", False, str(e))


def check_github(r, gh_token):
    env = {**__import__('os').environ, "GH_TOKEN": gh_token}

    result = subprocess.run(
        ["gh", "api", "/repos/PayControlLimited/PayControl", "--jq", ".name"],
        capture_output=True, text=True, env=env
    )
    r.check("GitHub: PayControl repo accessible",
            result.returncode == 0 and "PayControl" in result.stdout)

    result = subprocess.run(
        ["gh", "api", "/repos/PayControlLimited/PayControl-PCI", "--jq", ".name"],
        capture_output=True, text=True, env=env
    )
    r.check("GitHub: PayControl-PCI repo accessible",
            result.returncode == 0 and "PayControl" in result.stdout)

    result = subprocess.run(
        ["gh", "api", "graphql", "-f",
         'query={ organization(login: "PayControlLimited") { projectV2(number: 1) { title } } }'],
        capture_output=True, text=True, env=env
    )
    r.check("GitHub: project board accessible (read:project scope)",
            result.returncode == 0 and "errors" not in result.stdout)

    result = subprocess.run(
        ["gh", "api", "graphql", "-f",
         'query={ organization(login: "PayControlLimited") { projectV2(number: 1) { fields(first:20) { nodes { ... on ProjectV2SingleSelectField { name } } } } } }'],
        capture_output=True, text=True, env=env
    )
    r.check("GitHub: project board has Status field", "Status" in result.stdout)
    r.check("GitHub: project board has Priority field", "Priority" in result.stdout)


def main():
    r = Runner("Weekly Summary · Integration checks")

    r.check("Config: slack-tokens.json exists", TOKENS.exists())
    r.check("Config: contributor-names.json exists", NAMES.exists())

    if TOKENS.exists():
        config = json.loads(TOKENS.read_text())
        r.check("Config: reports_bot_token present", bool(config.get("reports_bot_token")))
        r.check("Config: paycontrol_reports_channel = C0ATQEBLT89",
                config.get("paycontrol_reports_channel") == "C0ATQEBLT89")
        token = config.get("reports_bot_token", "")
        if token:
            check_slack_post(r, token)

    if NAMES.exists():
        names = json.loads(NAMES.read_text())
        expected = {"alipas", "rasmusmiddendorff", "lirre8", "ErikWallin", "bol"}
        missing = expected - set(names.keys())
        r.check("Config: all known contributors in names cache",
                not missing, f"Missing: {missing}" if missing else "")

    snaps = sorted(SNAPSHOTS_WS.glob("snapshot-*.json"))
    r.check("Snapshot: weekly summary baseline exists (2026-05-20)",
            any("2026-05-20" in s.name for s in snaps))

    gh_token = get_gh_token()
    if gh_token:
        check_github(r, gh_token)
    else:
        r.check("GitHub: GH_TOKEN available", False, "Not found in openclaw.json")

    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
