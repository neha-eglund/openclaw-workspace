# OpenClaw Workspace

Personal OpenClaw agent workspace for automating engineering reports, security audits, and customer feedback triage for PayControl.

## What's in here

```
skills/                          # Agent skill definitions
  paycontrol-customer-feedback/  # Weekly customer feedback triage
  paycontrol-weekly-summary/         # Weekly engineering dashboard
  github-pentest/                    # GitHub security pen-testing
  github-pr-review/                  # Automated PR reviews
  github-dependency-audit/           # Dependency vulnerability audit
  github-security-summary/           # Consolidated nightly security summary
  github-security-updates/           # Security dependency update checks
  slack-format/                      # Slack mrkdwn formatting helper

config/                          # Configuration (secrets excluded from git)
  slack-tokens.example.json          # Template — copy to slack-tokens.json and fill in
  slack-webhooks.example.json        # Template — copy to slack-webhooks.json and fill in

memory/                          # Claude persistent memory files
AGENTS.md                        # Agent identity and behaviour guidelines
HEARTBEAT.md                     # Heartbeat task configuration
IDENTITY.md                      # Agent identity
SOUL.md                          # Agent values and principles
TOOLS.md                         # Tool usage guidelines
USER.md                          # User profile for Claude
paycontrol-automated-reports.md  # Full documentation of the two cron jobs
```

## Automated Cron Jobs

Two jobs run every Friday via OpenClaw cron (isolated agent sessions):

| Job | Time | What it does |
|---|---|---|
| `paycontrol-customer-feedback` | 07:30 Stockholm | Reads #paycontrol-feedback Slack channel, classifies feedback, matches to GitHub issues, posts triage report to #paycontrol-reports |
| `paycontrol-weekly-summary` | 07:50 Stockholm | Collects 7-day GitHub activity across 3 repos, posts 4-part engineering dashboard to #paycontrol-reports |

See [paycontrol-automated-reports.md](paycontrol-automated-reports.md) for full functional and technical documentation.

## Skills

Each skill is a folder containing a `SKILL.md` file that defines the agent's behaviour for that task. Skills are invoked by OpenClaw agents and can be customised by editing the `SKILL.md`.

To edit a skill, open `skills/<skill-name>/SKILL.md` and modify the instructions. Changes take effect on the next agent run.

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/neha-eglund/openclaw-workspace
cd openclaw-workspace
```

### 2. Configure Slack credentials

```bash
cp config/slack-tokens.example.json config/slack-tokens.json
cp config/slack-webhooks.example.json config/slack-webhooks.json
```

Edit both files and fill in your actual tokens. These files are gitignored and will never be committed.

### 3. Set GitHub token

The GitHub token (`GH_TOKEN`) is stored in the OpenClaw gateway config at:
```
~/.openclaw/openclaw.json → env.vars.GH_TOKEN
```

### 4. Open in VS Code

```bash
code .
```

## Customising the reports

### Change what the weekly summary includes

Edit `skills/paycontrol-weekly-summary/SKILL.md` — the prompt template controls exactly what data is collected, how it is formatted, and what gets highlighted.

### Change the customer feedback classification

Edit `skills/paycontrol-customer-feedback/SKILL.md` — the classification schema, matching confidence rules, and report format are all defined there.

### Add a new repo to the weekly summary

In the cron job prompt (manageable via OpenClaw UI), add the new repo to the repo list at the top.

### Reprocess full Slack history

Clear the snapshot file before the Friday run:
```bash
echo '{}' > ~/.openclaw/workspace/nightly-results/customer-feedback/last-run.json
```

## Requirements

- [OpenClaw](https://openclaw.dev) installed and running
- `gh` CLI authenticated with `repo` and `read:org` scopes
- Slack bot with `channels:history` scope, member of `#paycontrol-feedback`
- Incoming webhook for `#paycontrol-reports`
