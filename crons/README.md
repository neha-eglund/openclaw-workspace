# Cron Jobs

This folder contains the configuration for the two PayControl automated cron jobs.

| File | Job | Schedule |
|---|---|---|
| `paycontrol-customer-feedback.json` | Customer feedback triage | Fridays 07:30 Stockholm |
| `paycontrol-weekly-summary.json` | Weekly engineering dashboard | Fridays 07:50 Stockholm |

## Setup in a new environment

1. Fill in credentials:
   ```bash
   cp config/slack-tokens.example.json config/slack-tokens.json
   cp config/slack-webhooks.example.json config/slack-webhooks.json
   # Edit both files with real tokens
   ```

2. Set GitHub token in `~/.openclaw/openclaw.json` under `env.vars.GH_TOKEN`, or export it:
   ```bash
   export GH_TOKEN=ghp_...
   ```

3. Run the setup script:
   ```bash
   chmod +x crons/setup.sh
   ./crons/setup.sh
   ```

## Updating a job

The cron prompts reference the skill files directly — to change behaviour, edit the relevant `skills/<name>/SKILL.md` and push. The cron picks up changes automatically on the next run.

To change the schedule or other cron settings, update the `.json` file here and re-run `setup.sh`, or edit the job directly via `openclaw cron list` / `openclaw cron update`.
