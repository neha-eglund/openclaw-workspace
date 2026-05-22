# Tests — paycontrol-weekly-summary

Three layers of tests for the weekly engineering dashboard skill.

## How to run

```bash
# Static checks — run when you edit SKILL.md
python3 skills/paycontrol-weekly-summary/tests/tests.py

# Integration checks — GitHub API (requires internet + credentials)
python3 skills/paycontrol-weekly-summary/tests/test_integration.py

# Evals — LLM-as-judge scoring of a saved dry-run report
python3 skills/paycontrol-weekly-summary/tests/test_evals.py --file <path-to-log>
```

---

## Test files

| File | What it tests | Speed |
|---|---|---|
| `tests.py` | Static checks on `SKILL.md` — critical instructions present | Instant |
| `test_integration.py` | GitHub token validity, repo + project board access | ~5s |
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
- Does the board flow section require exactly 2 recommendations?

**When to run:** Any time you edit `SKILL.md`. Also runs automatically in CI on every push that touches `skills/`.

## Layer 2 — Integration checks (`test_integration.py`)

Calls the real APIs to verify the environment is correctly wired up.

What it checks:
- GitHub token can reach all three PayControl repos (`PayControl`, `PayControl-PCI`, `PayControl-GitOps`)
- GitHub token can query the PayControlLimited project board (requires `read:project` scope)
- Slack bot token is valid and can post to `#paycontrol-reports`
- All known contributor logins are in `contributor-names.json`
- At least one weekly snapshot exists so week-over-week deltas will work

In CI, tokens are read from `SLACK_TOKEN` and `GH_TOKEN` environment variables (GitHub Actions secrets). Locally they are read from `config/slack-tokens.json` and `~/.openclaw/openclaw.json`.

**When to run:** After changing credentials or setting up on a new machine.

## Layer 3 — Evals (`test_evals.py`)

Scores a saved dry-run report against quality criteria using Claude Haiku. Each criterion gets a PASS / FAIL / PARTIAL verdict with a one-sentence explanation.

Requires `ANTHROPIC_API_KEY` in your environment:

```bash
pip3 install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

Example criteria it checks:
- Are stale items described as "waiting for a decision" rather than "abandoned"?
- Are cycle time and review time written in plain English, not raw statistics?
- Does the board flow section end with exactly 2 specific recommendations?
- Are all Slack section headings bold (`*heading*`)?

To generate a report to eval:

```bash
export DRY_RUN=true
# invoke the skill normally — output prints to stdout instead of posting to Slack
```

---

## Credentials

| Credential | Where it lives | Used for |
|---|---|---|
| `reports_bot_token` | `config/slack-tokens.json` | Posting to `#paycontrol-reports` |
| `GH_TOKEN` | `~/.openclaw/openclaw.json` → `env.vars.GH_TOKEN` | GitHub API calls |
| `contributor-names.json` | `config/contributor-names.json` | Login → full name cache |
