"""
Central config for paycontrol-weekly-summary scripts.

All credentials and paths are resolved here. Override with environment variables
to run in GitHub Actions, Docker, or any other environment.

Environment variables:
    GH_TOKEN              GitHub personal access token
    REPORTS_BOT_TOKEN     Slack bot token for posting to #paycontrol-reports
    SLACK_CHANNEL_ID      Slack channel ID (default: C0ATQEBLT89)
    WORKSPACE_DIR         Base workspace directory
                          (default: ~/.openclaw/workspace)
    RESULTS_DIR           Where snapshots and chart PNGs are saved
                          (default: WORKSPACE_DIR/nightly-results/weekly-summary)
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
    WORKSPACE_DIR / "nightly-results" / "weekly-summary"
))

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config files (used as fallback when env vars are not set) ───────────────

_TOKENS_FILE = WORKSPACE_DIR / "config" / "slack-tokens.json"
_OPENCLAW_FILE = Path(os.path.expanduser("~/.openclaw/openclaw.json"))


def _load_tokens():
    if _TOKENS_FILE.exists():
        return json.loads(_TOKENS_FILE.read_text())
    return {}


def _load_gh_token():
    if _OPENCLAW_FILE.exists():
        return json.loads(_OPENCLAW_FILE.read_text())["env"]["vars"]["GH_TOKEN"]
    return None


# ── Credentials ─────────────────────────────────────────────────────────────

GH_TOKEN = os.environ.get("GH_TOKEN") or _load_gh_token()

_tokens = _load_tokens()
REPORTS_BOT_TOKEN = os.environ.get("REPORTS_BOT_TOKEN") or _tokens.get("reports_bot_token")
SLACK_CHANNEL_ID  = os.environ.get("SLACK_CHANNEL_ID")  or _tokens.get("paycontrol_reports_channel", "C0ATQEBLT89")

# ── Other config files ───────────────────────────────────────────────────────

CONTRIBUTOR_NAMES_FILE = WORKSPACE_DIR / "config" / "contributor-names.json"

# ── Snapshot paths ───────────────────────────────────────────────────────────

SNAPSHOT_DIR = RESULTS_DIR  # snapshots live alongside charts: snapshot-YYYY-MM-DD.json

# ── Temp files (ephemeral, always /tmp) ─────────────────────────────────────

TMP_WINDOW       = "/tmp/ws_window.json"
TMP_BOARD        = "/tmp/ws_board.json"
TMP_STATS        = "/tmp/ws_stats.json"
TMP_DELTAS       = "/tmp/ws_deltas.json"
TMP_REPORT       = "/tmp/ws_report.json"
TMP_REPO_PREFIX  = "/tmp/ws_"  # e.g. /tmp/ws_merged_prs_PayControlLimited_PayControl.json
