# Tests — paycontrol-customer-feedback

Three layers of tests for the customer feedback triage skill.

## How to run

```bash
# Static checks — run when you edit SKILL.md
python3 skills/paycontrol-customer-feedback/tests/tests.py

# Integration checks — Slack + GitHub APIs (requires internet + credentials)
python3 skills/paycontrol-customer-feedback/tests/test_integration.py

# Evals — LLM-as-judge scoring of a saved dry-run report
python3 skills/paycontrol-customer-feedback/tests/test_evals.py --file <path-to-log>
```

---

## Test files

| File | What it tests | Speed |
|---|---|---|
| `tests.py` | Static checks on `SKILL.md` — critical instructions present | Instant |
| `test_integration.py` | Slack bot token validity, channel access, GitHub connectivity | ~5s |
| `test_evals.py` | LLM-as-judge quality scoring of a saved report | ~30s |
| `helpers.py` | Shared utilities — token loading, imported by other test files | — |

---

## Layer 1 — Static checks (`tests.py`)

Reads `SKILL.md` and uses regex to verify critical instructions are present. No network calls.

Examples of what it checks:
- Is `chat.postMessage` used (not the old webhook)?
- Is `thread_ts` present (required for thread replies)?
- Is the `DRY_RUN` flag present so test runs don't post to Slack?
- Are contributor names resolved before output is generated?

**When to run:** Any time you edit `SKILL.md`. Also runs automatically in CI on every push that touches `skills/`.

## Layer 2 — Integration checks (`test_integration.py`)

Calls the real APIs to verify the environment is correctly wired up.

What it checks:
- `slack-tokens.json` exists and the bot token is valid (`auth.test`)
- `#paycontrol-feedback` is readable by the bot (`channels:history` scope)
- `#paycontrol-reports` is accessible and the bot is a member
- GitHub token can reach all three PayControl repos and the project board
- All known contributor logins are in `contributor-names.json`

In CI, tokens are read from `SLACK_TOKEN` and `GH_TOKEN` environment variables (GitHub Actions secrets). Locally they are read from `config/slack-tokens.json` and `~/.openclaw/openclaw.json`.

**When to run:** After changing credentials or setting up on a new machine.

## Layer 3 — Evals (`test_evals.py`)

Scores a saved dry-run report against quality criteria using Claude Haiku. Each criterion gets a PASS / FAIL / PARTIAL verdict with a one-sentence explanation.

Requires `ANTHROPIC_API_KEY` in your environment:

```bash
pip3 install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

To generate a report to eval:

```bash
export DRY_RUN=true
# invoke the skill normally — output prints to stdout instead of posting to Slack
```

---

## Credentials

| Credential | Where it lives | Used for |
|---|---|---|
| `bot_token` | `config/slack-tokens.json` | Reading `#paycontrol-feedback` |
| `reports_bot_token` | `config/slack-tokens.json` | Posting to `#paycontrol-reports` |
| `GH_TOKEN` | `~/.openclaw/openclaw.json` → `env.vars.GH_TOKEN` | GitHub API calls |
| `contributor-names.json` | `config/contributor-names.json` | Login → full name cache |
