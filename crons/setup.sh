#!/bin/bash
# Register PayControl cron jobs in OpenClaw.
# Run once per environment after cloning the repo and filling in config/slack-tokens.json.
#
# Usage:
#   chmod +x crons/setup.sh
#   ./crons/setup.sh
#
# Prerequisites:
#   - OpenClaw CLI installed and authenticated (openclaw login)
#   - config/slack-tokens.json filled in  (copy from config/slack-tokens.example.json)
#   - GH_TOKEN set in ~/.openclaw/openclaw.json env.vars.GH_TOKEN
#     OR exported as an environment variable: export GH_TOKEN=ghp_...

set -e

WORKSPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Load credentials
SLACK_TOKEN=$(python3 -c "import json; print(json.load(open('$WORKSPACE_DIR/config/slack-tokens.json'))['bot_token'])")

if [ -z "$GH_TOKEN" ]; then
  GH_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.openclaw/openclaw.json'))['env']['vars']['GH_TOKEN'])" 2>/dev/null || true)
fi

if [ -z "$SLACK_TOKEN" ] || [ "$SLACK_TOKEN" = "xoxb-YOUR-BOT-TOKEN-HERE" ]; then
  echo "ERROR: SLACK_TOKEN not set. Fill in config/slack-tokens.json first."
  exit 1
fi

if [ -z "$GH_TOKEN" ]; then
  echo "ERROR: GH_TOKEN not set. Export it or add to ~/.openclaw/openclaw.json."
  exit 1
fi

echo "Registering paycontrol-customer-feedback..."
openclaw cron add \
  --name "paycontrol-customer-feedback" \
  --description "Weekly customer feedback report — reads #paycontrol-feedback, classifies items, matches to GitHub issues, posts to #paycontrol-reports. Runs every Friday at 07:30 Stockholm time." \
  --schedule-kind cron \
  --schedule-expr "30 7 * * 5" \
  --schedule-tz "Europe/Stockholm" \
  --session-target isolated \
  --delivery-mode none \
  --model claude-sonnet-4-6 \
  --timeout 1800 \
  --message "Read the skill file at $WORKSPACE_DIR/skills/paycontrol-customer-feedback/SKILL.md and execute all instructions in it exactly as written.

Credentials:
- SLACK_TOKEN=$SLACK_TOKEN
- GH_TOKEN=$GH_TOKEN

Set both as env vars before running."

echo "Registering paycontrol-weekly-summary..."
openclaw cron add \
  --name "paycontrol-weekly-summary" \
  --description "Weekly engineering dashboard — collects 7-day GitHub activity across 3 repos, posts 4-part report to #paycontrol-reports. Runs every Friday at 07:50 Stockholm time." \
  --schedule-kind cron \
  --schedule-expr "50 7 * * 5" \
  --schedule-tz "Europe/Stockholm" \
  --session-target isolated \
  --delivery-mode none \
  --model claude-sonnet-4-6 \
  --timeout 1800 \
  --message "Read the skill file at $WORKSPACE_DIR/skills/paycontrol-weekly-summary/SKILL.md and execute all instructions in it exactly as written.

Credentials:
- GH_TOKEN=$GH_TOKEN

Set GH_TOKEN as an env var before running."

echo ""
echo "Done. Both cron jobs registered."
echo "  paycontrol-customer-feedback  — Fridays 07:30 Stockholm"
echo "  paycontrol-weekly-summary     — Fridays 07:50 Stockholm"
echo ""
echo "Verify with: openclaw cron list"
