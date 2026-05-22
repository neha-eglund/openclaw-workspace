"""
Central config for paycontrol-customer-requirements scripts.

All credentials and paths are resolved here. Override with environment variables
to run in GitHub Actions, Docker, or any other environment.

Environment variables:
    GH_TOKEN              GitHub personal access token
    SLACK_TOKEN           Slack bot token for reading #paycontrol-feedback
    REPORTS_BOT_TOKEN     Slack bot token for posting to #paycontrol-reports
    SLACK_CHANNEL_ID      Feedback channel ID (default: C0AKQRQ6QDA)
    REPORTS_CHANNEL_ID    Reports channel ID (default: C0ATQEBLT89)
    WORKSPACE_DIR         Base workspace directory
                          (default: ~/.openclaw/workspace)
    RESULTS_DIR           Where snapshots, reports, and supplements are saved
                          (default: WORKSPACE_DIR/nightly-results/customer-feedback)
"""
import json, os
from pathlib import Path

# ── Base directories ────────────────────────────────────────────────────────

WORKSPACE_DIR = Path(os.environ.get(
    "WORKSPACE_DIR",
    os.path.expanduser("~/.openclaw/workspace")
))

RESULTS_DIR = Path(os.environ.get(
    "RESULTS_DIR",
    WORKSPACE_DIR / "nightly-results" / "customer-feedback"
))

# ── Config files (used as fallback when env vars are not set) ───────────────

_TOKENS_FILE   = WORKSPACE_DIR / "config" / "slack-tokens.json"
_OPENCLAW_FILE = Path(os.path.expanduser("~/.openclaw/openclaw.json"))


def _load_tokens():
    if _TOKENS_FILE.exists():
        return json.loads(_TOKENS_FILE.read_text())
    return {}


def _load_gh_token():
    if _OPENCLAW_FILE.exists():
        try:
            return json.loads(_OPENCLAW_FILE.read_text())["env"]["vars"]["GH_TOKEN"]
        except (KeyError, json.JSONDecodeError):
            pass
    return None


# ── Credentials ─────────────────────────────────────────────────────────────

_tokens = _load_tokens()

GH_TOKEN           = os.environ.get("GH_TOKEN")           or _load_gh_token()
SLACK_TOKEN        = os.environ.get("SLACK_TOKEN")        or _tokens.get("bot_token")
REPORTS_BOT_TOKEN  = os.environ.get("REPORTS_BOT_TOKEN")  or _tokens.get("reports_bot_token")
SLACK_CHANNEL_ID   = os.environ.get("SLACK_CHANNEL_ID")   or "C0AKQRQ6QDA"
REPORTS_CHANNEL_ID = os.environ.get("REPORTS_CHANNEL_ID") or _tokens.get("paycontrol_reports_channel", "C0ATQEBLT89")

# ── Other config files ───────────────────────────────────────────────────────

CONTRIBUTOR_NAMES_FILE = WORKSPACE_DIR / "config" / "contributor-names.json"

# ── Snapshot and output paths ────────────────────────────────────────────────

SNAPSHOT_DIR    = RESULTS_DIR / "snapshots"
LAST_RUN_FILE   = RESULTS_DIR / "last-run.json"
SUPPLEMENTS_DIR = RESULTS_DIR / "supplements"
REPORTS_DIR     = RESULTS_DIR

for _d in [SNAPSHOT_DIR, SUPPLEMENTS_DIR, SUPPLEMENTS_DIR / "processed"]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Temp files (ephemeral, always /tmp) ─────────────────────────────────────

TMP_MESSAGES     = "/tmp/cf_messages.json"
TMP_THREADS      = "/tmp/cf_threads.json"
TMP_RESOLVED     = "/tmp/cf_reaction_resolved.json"
TMP_ACKNOWLEDGED = "/tmp/cf_reaction_acknowledged.json"
TMP_WINDOW       = "/tmp/cf_window.json"
TMP_BOARD        = "/tmp/cf_board.json"
TMP_ALL_ISSUES   = "/tmp/cf_all_issues.json"
TMP_ISSUE_PRS    = "/tmp/cf_issue_to_prs.json"
TMP_ITEMS        = "/tmp/cf_feedback_items.json"
TMP_DELTAS       = "/tmp/cf_deltas.json"
TMP_REPORT       = "/tmp/cf_report.json"
