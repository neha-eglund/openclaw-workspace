# PayControl Skill Tests

Tests for the two PayControl cron skills: `paycontrol-customer-feedback` and `paycontrol-weekly-summary`.

## How to run

```bash
# Per-skill static checks — run these when you edit a skill
python3 skills/paycontrol-customer-feedback/tests.py
python3 skills/paycontrol-weekly-summary/tests.py

# Integration checks — Slack + GitHub APIs (requires internet)
python3 tests/test_integration.py

# Evals — score a saved dry-run report with LLM-as-judge
python3 tests/test_evals.py --file tests/logs/2026-05-21-11-58.log --skill summary
python3 tests/test_evals.py --file tests/logs/2026-05-21-11-58.log --skill feedback
```

---

## Test files

Static checks live inside each skill directory so they can be committed and updated independently:

| File | What it tests | Speed |
|---|---|---|
| `skills/paycontrol-customer-feedback/tests.py` | Customer feedback skill — static checks | Instant |
| `skills/paycontrol-weekly-summary/tests.py` | Weekly summary skill — static checks | Instant |
| `tests/test_integration.py` | Slack + GitHub API connectivity + config | ~5s |
| `tests/test_evals.py` | LLM-as-judge quality scoring of a saved report | ~30s |
| `tests/helpers.py` | Shared utilities — imported by all test files | — |

---

## The three layers

### Layer 1 — Static checks

Reads the `SKILL.md` files and uses regex to verify that critical instructions are present. No network calls, runs in under a second.

Examples of what it checks:
- Is `chat.postMessage` used (not the old webhook)?
- Is `thread_ts` present (required for thread replies)?
- Does Thread reply 2 source cumulative open questions (not just this week)?
- Is the `DRY_RUN` flag present so test runs don't post to Slack?
- Are contributor names resolved before output is generated?

**When to run:** Any time you edit a `SKILL.md` file. If you accidentally remove a critical instruction, this catches it immediately.

### Layer 2 — Integration checks

Calls the real APIs to verify the environment is correctly wired up. Requires internet access and valid credentials in `config/`.

What it checks:
- `slack-tokens.json` exists and the bot token is valid (`auth.test`)
- `#paycontrol-feedback` is readable by the bot (`channels:history` scope)
- `#paycontrol-reports` is accessible and the bot is a member
- GitHub token can reach all three PayControl repos and the project board
- All 5 known contributor logins are in `contributor-names.json`
- Snapshot files exist so week-over-week deltas will work on the next run

**When to run:** After changing credentials, adding a new Slack bot, or setting up the workspace on a new machine.

### Layer 3 — Evals (LLM-as-judge)

Takes the output of a dry-run report (a saved text file) and scores it against a checklist of quality criteria using Claude Haiku. Each criterion gets a PASS / FAIL / PARTIAL verdict with a one-sentence explanation.

Requires `ANTHROPIC_API_KEY` to be set in your environment. Install the SDK first if needed:

```bash
pip3 install anthropic
```

Example criteria it checks:
- Are stale items described as "waiting for a decision" rather than "abandoned"?
- Does the main message contain only this week's new items (not cumulative history)?
- Are all section headings in Slack bold (`*heading*`)?
- Are cycle time and review time written in plain English, not raw statistics?
- Does the board flow section end with exactly 2 specific recommendations?

**When to run:** After a dry-run to verify the report quality before enabling Slack posting, or when you've made significant changes to the report format.

To generate a dry-run report to eval, run the skill with `DRY_RUN = True` in the posting step and save the webchat output to a file.

---

## Credentials required for Layer 2

| File | What it's used for |
|---|---|
| `config/slack-tokens.json` | Bot token for Slack API calls |
| `config/contributor-names.json` | Login → full name cache |
| `~/.openclaw/openclaw.json` | GitHub token (`GH_TOKEN`) |
