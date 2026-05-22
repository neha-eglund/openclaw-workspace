# OpenClaw Workspace

Personal OpenClaw agent workspace for automating engineering reports, security audits, and customer feedback triage for PayControl.

## What's in here

```
skills/                              # Agent skill definitions
  paycontrol-customer-feedback/      # Weekly customer feedback triage
  paycontrol-weekly-summary/         # Weekly engineering dashboard
  github-pentest/                    # GitHub security pen-testing
  github-pr-review/                  # Automated PR reviews
  github-dependency-audit/           # Dependency vulnerability audit
  github-security-summary/           # Consolidated nightly security summary
  github-security-updates/           # Security dependency update checks
  slack-format/                      # Slack mrkdwn formatting helper

config/                              # Configuration (secrets excluded from git)
  slack-tokens.example.json          # Template — copy to slack-tokens.json and fill in
                                     #   Keys: bot_token, reports_bot_token,
                                     #         paycontrol_feedback_channel,
                                     #         paycontrol_reports_channel

memory/                              # Claude persistent memory files
AGENTS.md                            # Agent identity and behaviour guidelines
HEARTBEAT.md                         # Heartbeat task configuration
IDENTITY.md                          # Agent identity
SOUL.md                              # Agent values and principles
TOOLS.md                             # Tool usage guidelines
USER.md                              # User profile for Claude
paycontrol-automated-reports.md      # Full documentation of the two cron jobs
```

## Automated Cron Jobs

Two jobs run every Friday via OpenClaw cron (isolated agent sessions):

| Job | Time | What it does |
|---|---|---|
| `paycontrol-customer-feedback` | 07:30 Stockholm | Reads #paycontrol-feedback Slack channel, classifies feedback, matches to GitHub issues, posts triage report to #paycontrol-reports |
| `paycontrol-weekly-summary` | 07:50 Stockholm | Collects 7-day GitHub activity across 3 repos, posts 4-part engineering dashboard to #paycontrol-reports |

See [paycontrol-automated-reports.md](paycontrol-automated-reports.md) for full functional and technical documentation.

## Skills

Each skill is a self-contained folder with:
- `SKILL.md` — agent instructions
- `scripts/` — Python scripts for data fetching, snapshot saving, and Slack posting
- `tests/` — static checks, integration tests, and LLM eval tests

To edit a skill, open `skills/<skill-name>/SKILL.md`. Changes take effect on the next agent run.

## CI Pipeline

A GitHub Actions workflow (`.github/workflows/skills-ci.yml`) runs on every push or PR that touches `skills/`. It runs:

1. **Lint** — `ruff` (E/W/F rules)
2. **Type check** — `mypy` per skill
3. **Unit tests** — static checks for both skills
4. **Integration tests** — Slack + GitHub API connectivity (uses `GH_TOKEN` and `SLACK_TOKEN` secrets)

## Dry Run

Both skills support `DRY_RUN=true` — the full pipeline runs but Slack posting is skipped and the report is printed to stdout instead:

```bash
export DRY_RUN=true
# then invoke the skill normally
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/neha-eglund/openclaw-workspace
cd openclaw-workspace
```

### 2. Configure Slack credentials

```bash
cp config/slack-tokens.example.json config/slack-tokens.json
```

Edit the file and fill in your actual tokens. This file is gitignored and will never be committed.

Required keys:
- `bot_token` — reads `#paycontrol-feedback`
- `reports_bot_token` — posts to `#paycontrol-reports`
- `paycontrol_feedback_channel` — channel ID for `#paycontrol-feedback`
- `paycontrol_reports_channel` — channel ID for `#paycontrol-reports`

### 3. Set GitHub token

The GitHub token (`GH_TOKEN`) is stored in the OpenClaw gateway config at:
```
~/.openclaw/openclaw.json → env.vars.GH_TOKEN
```

### 4. Register cron jobs

```bash
chmod +x crons/setup.sh
./crons/setup.sh
```

## Customising the reports

### Change what the weekly summary includes

Edit `skills/paycontrol-weekly-summary/SKILL.md` — the prompt template controls what data is collected, how it is formatted, and what gets highlighted.

### Change the customer feedback classification

Edit `skills/paycontrol-customer-feedback/SKILL.md` — the classification schema, matching confidence rules, and report format are all defined there.

### Add a new repo to the weekly summary

Set the `REPOS` environment variable (comma-separated) before running, or update the default in `skills/paycontrol-weekly-summary/scripts/config.py`.

### Reprocess full Slack history

Clear the last-run file before the Friday run:
```bash
echo '{"last_ts": "0"}' > ~/.openclaw/workspace/nightly-results/customer-feedback/last-run.json
```

## Requirements

- [OpenClaw](https://openclaw.dev) installed and running
- `gh` CLI authenticated with `repo` and `read:org` scopes
- Slack bot token with `channels:history`, `reactions:read`, and `users:read` scopes, member of `#paycontrol-feedback`
- Slack bot token with `chat:write` scope for posting to `#paycontrol-reports`
