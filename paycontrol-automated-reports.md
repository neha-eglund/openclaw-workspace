# PayControl Automated Reports — Documentation

**Last updated:** 2026-05-13
**Owner:** neha.eglund@devcode.se
**Platform:** OpenClaw cron (isolated agent sessions)

---

## Overview

Two automated Claude agent jobs run every Friday morning and post reports to **#paycontrol-reports** on Slack. They run sequentially — customer feedback first at 07:30, then the engineering summary at 07:50.

| Job | Schedule | Output |
|---|---|---|
| `paycontrol-customer-feedback` | Friday 07:30 Stockholm | 1 Slack message — customer feedback triage report |
| `paycontrol-weekly-summary` | Friday 07:50 Stockholm | 4 Slack messages — engineering dashboard |

Both jobs run in **isolated sessions** (ephemeral, no impact on the main Claude session) and use `claude-sonnet-4-6` with a 30-minute timeout.

---

---

# Job 1 — paycontrol-customer-feedback

## Functional Overview

Reads every message posted to the private Slack channel **#paycontrol-feedback** since the last run, classifies each piece of feedback, cross-references it against the GitHub project board and open PRs, and posts a structured triage report to **#paycontrol-reports**.

**Purpose:** Give the team a weekly view of what customers are reporting, whether it is already tracked in GitHub, who is working on it, and what still needs a ticket created.

**Audience:** Product, engineering, and support — anyone who needs to know the state of customer-reported issues.

### What the report contains

The report is split into four sections:

| Section | Meaning |
|---|---|
| ✅ Resolved | Issue is closed and/or a PR has been merged that fixes it |
| 🔧 Tracked | An open GitHub issue was found matching the feedback |
| ❌ Not tracked | No matching GitHub issue found, or match confidence was too low |
| ⚠️ Needs triage | Action list — items needing a new GitHub issue, or tracked items needing a PR |

Each item includes:
- **Category** — Bug / Feature Request / UX / Compliance / Integration / Analytics
- **Severity** — 🔴 Blocking / 🟡 High / 🔵 Normal
- **Who raised it** — extracted from message text (e.g. "Erik at MerchantX")
- **Linked GitHub issue** and **linked PRs** (with status: open/merged)
- **Worked on by** — all GitHub logins who touched the issue (assignees, PR authors, commenters)
- **Match confidence** — how certain the GitHub match is (definitive / high)
- For untracked items: a `_Question:_` (what was raised) and `_Conclusion:_` (what the thread resolved)

### Classification rules

**Severity:**
- 🔴 Blocking — customer cannot proceed, escalation or churn risk, or regulatory obligation
- 🟡 High — significant friction, compliance risk, or explicitly time-sensitive
- 🔵 Normal — improvement request, no stated urgency

**GitHub matching confidence:**
- `definitive` — a GitHub issue URL was found directly in the Slack thread
- `high` — 3+ exact technical terms (component name, error message, flow name) match the issue title/body
- `medium` / `low` — automatically demoted to ❌ Not tracked (conservative by design — wrong matches are worse than no match)

---

## Technical Overview

### Cron job details

| Field | Value |
|---|---|
| Job ID | `3c8a5f04-8355-40fa-8021-7c21e5783ce1` |
| Schedule | `30 7 * * 5` (Friday 07:30, Europe/Stockholm) |
| Session target | `isolated` |
| Model | `claude-sonnet-4-6` |
| Timeout | 1800 seconds |
| Delivery | `none` |
| Last run | 2026-05-08 ✅ (16 items found) |
| Next run | 2026-05-15 07:30 |

### Skill definition

Full logic is defined in:
`/Users/nehaeglund/.openclaw/workspace/skills/paycontrol-customer-feedback/SKILL.md`

The cron job prompt is a condensed version of this skill. The skill file is the source of truth.

### Step-by-step execution

#### Step 1 — Load snapshot

Reads the snapshot file to determine the start of the fetch window:

```
/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/last-run.json
```

Example snapshot:
```json
{
  "last_ts": "1778218605.025296",
  "last_date": "2026-05-08",
  "window_from": "2026-03-10",
  "window_to": "2026-05-08",
  "items_found": 16
}
```

- `last_ts` — Slack timestamp of the last fetched message. Only messages newer than this are fetched on the next run.
- If the file is empty (`{}`) or missing — fetches from the very beginning of the channel (first-ever run behaviour).

**To reprocess full channel history:** clear the file to `{}` before 07:30 Friday.

#### Step 2 — Read Slack messages

Calls the Slack API using the bot token:

```
GET https://slack.com/api/conversations.history
  channel=C0AKQRQ6QDA
  oldest=<last_ts>
  limit=200
```

For any message with `reply_count > 0`, also fetches the full thread:

```
GET https://slack.com/api/conversations.replies
  channel=C0AKQRQ6QDA
  ts=<message_ts>
```

Parent message + all replies are concatenated into a single `full_context` string per item. This is the primary input for all classification and matching decisions.

#### Step 3 — Fetch GitHub project board

Queries `PayControlLimited/projects/1` via GitHub GraphQL API (first 200 items) to get issue numbers, titles, states, and board column (Status field). Result saved to `/tmp/project_items.json`.

#### Step 3b — Build issue → PR index

Fetches recent PRs from all three repos:
- `PayControlLimited/PayControl`
- `PayControlLimited/PayControl-PCI`
- `PayControlLimited/PayControl-GitOps`

Builds an index of which PRs close which issues using:
1. `closingIssuesReferences` from the GitHub GraphQL PR response
2. `closes/fixes/resolves #NNN` patterns in PR body/title
3. Bare `#NNN` references in PR titles

#### Step 4 — Classify and match each feedback item

For each Slack message:

1. Extract the core feedback (one-line summary of the actual problem, not the phrasing)
2. Classify Category and Severity
3. Note resolution signals in the thread ("accessible now", "fix on the way", "removed")
4. Extract who raised it from message text patterns — never resolves Slack user IDs
5. Derive 2–4 specific technical search phrases from the thread (component names, error messages, flow names — not vague keywords)
6. Run targeted `gh issue list --search` against the repos using those phrases
7. Read title AND body of each result to evaluate match confidence
8. For accepted matches (definitive/high): collect `worked_on_by` from assignees, issue events, PR authors, and comment authors

#### Step 5 — Build and post report

Assembles the full structured report with all four sections (Resolved, Tracked, Not Tracked, Needs Triage), sorted Blocking → High → Normal within each section.

Saves updated snapshot to `last-run.json`.

Posts the full report (not a digest) to `#paycontrol-reports` via incoming webhook.

### Slack integration

Two separate Slack integrations:

| Integration | API | Purpose | Credential location |
|---|---|---|---|
| Bot token (`xoxb-...`) | `conversations.history`, `conversations.replies` | Read messages from #paycontrol-feedback | `/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json` |
| Incoming webhook | HTTP POST | Post report to #paycontrol-reports | `/Users/nehaeglund/.openclaw/workspace/config/slack-webhooks.json` → key `paycontrol-reports` |

The browser is never used — all Slack access goes through the API directly via `curl`. The bot is a member of `#paycontrol-feedback` and has `channels:history` scope.

All GitHub links in the Slack message use pipe-link format: `<https://github.com/.../issues/NNN|Issue #NNN>` so only the short label is visible and clickable.

### Key files

| File | Purpose |
|---|---|
| `nightly-results/customer-feedback/last-run.json` | Run snapshot — controls time window |
| `config/slack-tokens.json` | Bot token for reading #paycontrol-feedback |
| `config/slack-webhooks.json` | Webhook URL for posting to #paycontrol-reports |
| `skills/paycontrol-customer-feedback/SKILL.md` | Full skill definition |

---

---

# Job 2 — paycontrol-weekly-summary

## Functional Overview

Queries the rolling last 7 days of activity across all three PayControl GitHub repositories and posts a **4-part engineering dashboard** to **#paycontrol-reports** on Slack.

**Purpose:** Give the whole team a weekly celebration of what shipped, who delivered it, what is blocked or stale, and what security/maintenance items need attention.

**Audience:** The full engineering team — developers, tech lead, stakeholders.

### What the report contains — 4 Slack messages

Messages are sent 60 seconds apart so each lands as a distinct, readable block.

**Message 1 — Header snapshot** (immediate)
- Total PRs merged, issues closed, contributors
- Per-repo stats in a code block: PRs / Issues Closed / In Progress / In Review / Security

**Message 2 — Team Spotlights + Key Deliveries** (+60s)
```
━━━━━━━━━━━━━━━━━━━━━━
⭐ TEAM SPOTLIGHTS

• @login — Y issues closed · X PRs merged · one sentence on biggest impact
  (issues omitted if 0 — never shows "0 issues")

━━━━━━━━━━━━━━━━━━━━━━
🔑 KEY DELIVERIES

── PayControl ──
• emoji *Title* — 5-6 word description. @author · Issue #NNN · PR #NNN

── PayControl-PCI ──
── PayControl-GitOps ──
```

**Message 3 — Stale items** (+120s)
- Stale board issues (In Progress or In Review > 7 days): 🔴 >30d, 🟡 >7d
- Stale open PRs: 🔴 >30d, 🟠 >14d, 🟡 >7d
- Count of merged PRs with no linked issue (nudge to link issues before starting work)

**Message 4 — Action items + Contributors** (+180s)
- Ranked action items: security CVEs by age, stale board issues, stale PRs
- Per-contributor stats: PRs (tracked/untracked), issues closed, repos
- Total line

### Key definitions

**Tracked PR** — has a linked issue via `closingIssuesReferences` or `closes/fixes/resolves #NNN` pattern in PR body/title.

**Untracked PR** — merged with no linked issue.

**Issues closed** — issues closed within the 7-day window. Attributed to the PR author if the issue has no assignee.

**Stale board issue** — open issue on `PayControlLimited/projects/1` sitting in "In Progress" or "In Review" for more than 7 days with no update.

---

## Technical Overview

### Cron job details

| Field | Value |
|---|---|
| Job ID | `f3fe8f53-f27c-4f73-9d2d-a427949572a5` |
| Schedule | `50 7 * * 5` (Friday 07:50, Europe/Stockholm) |
| Session target | `isolated` |
| Model | `claude-sonnet-4-6` |
| Timeout | 1800 seconds |
| Delivery | `none` |
| Last run | 2026-05-08 ✅ (~4 min runtime) |
| Next run | 2026-05-15 07:50 |

### Skill definition

Full logic is defined in:
`/Users/nehaeglund/.openclaw/workspace/skills/paycontrol-weekly-summary/SKILL.md`

### Step-by-step execution

#### Step 1 — Compute time window

```bash
SINCE=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)   # 7 days ago in UTC
TODAY=$(date +%Y-%m-%d)
```

#### Step 2 — Fetch merged PRs

For each of the three repos:
```bash
gh pr list --repo <repo> --state merged --search "merged:>=$SINCE" \
  --json number,title,author,body,mergedAt,closingIssuesReferences
```

Builds a tracked/untracked split per contributor using `closingIssuesReferences` and `closes/fixes/resolves` body patterns.

#### Step 3 — Fetch closed issues

```bash
gh issue list --repo <repo> --state closed \
  --search "closed:>=$SINCE" \
  --json number,title,assignees,closedAt
```

For issues with no assignee, falls back to the PR author via issue events API:
```bash
gh api repos/<repo>/issues/<number>/events
```
Looks for a `closed` event and takes the actor's login.

#### Step 4 — Fetch stale open PRs

```bash
gh pr list --repo <repo> --state open \
  --json number,title,author,createdAt,reviews,url
```

Computes age from `createdAt`. Flags 🔴 >30d / 🟠 >14d / 🟡 >7d.

#### Step 5 — Fetch security issues

```bash
gh issue list --repo <repo> --state open \
  --label "security" --json number,title,createdAt,assignees
```

Also queries issues labelled "vulnerability". Counts per repo for the header snapshot.

#### Step 6 — Query project board (if accessible)

Queries `PayControlLimited/projects/1` via GraphQL for items in "In Progress" or "In Review" columns. Computes age from `updatedAt`. Flags stale items.

Note: this step requires `read:project` scope on the GitHub token. If the scope is missing, the board section is skipped.

#### Step 7 — Post 4 Slack messages

Loads the webhook URL:
```python
webhook = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-webhooks.json'))['paycontrol-reports']
```

Posts Message 1 immediately. Schedules Messages 2, 3, 4 as background shell processes with 60s delays:
```bash
(sleep 60  && python3 /tmp/post_msg2.py) &
(sleep 120 && python3 /tmp/post_msg3.py) &
(sleep 180 && python3 /tmp/post_msg4.py) &
```

### Slack integration

Single integration — outbound only:

| Integration | Purpose | Credential location |
|---|---|---|
| Incoming webhook | Post 4 messages to #paycontrol-reports | `/Users/nehaeglund/.openclaw/workspace/config/slack-webhooks.json` → key `paycontrol-reports` |

No Slack read access needed for this job — it only reads from GitHub.

All GitHub links use pipe-link format: `<https://github.com/.../pull/NNN|PR #NNN>`.

Slack formatting rules applied:
- `*bold*` for section headers and contributor names
- Triple-backtick code blocks for the repo stats table (ensures aligned columns)
- Bullet lists for all other structured content (no pipe tables — they render as raw text in Slack)
- `━━━━━━━━━━━━━━━━━━━━━━` dividers between major sections in Message 2

### Key files

| File | Purpose |
|---|---|
| `config/slack-webhooks.json` | Webhook URL for posting to #paycontrol-reports |
| `skills/paycontrol-weekly-summary/SKILL.md` | Full skill definition |
| `nightly-results/weekly-summary/snapshot-<date>.json` | Week-over-week trend data (written each run) |

---

---

# Shared Reference

## Credentials

| Secret | Location | Used by |
|---|---|---|
| Slack bot token | `config/slack-tokens.json` → `bot_token` | customer-feedback (read) |
| Slack webhook | `config/slack-webhooks.json` → `paycontrol-reports` | both jobs (write) |
| GitHub token | Embedded in cron job payload | both jobs |

## How to manage the jobs

**Trigger a job manually (right now):**
> "Trigger paycontrol-customer-feedback now"
> "Trigger paycontrol-weekly-summary now"

**Check last run status and logs:**
> "Show last run for paycontrol-customer-feedback"
> "Show last run for paycontrol-weekly-summary"

**Change the schedule:**
> "Change paycontrol-weekly-summary to run at 08:00"

**Reprocess full Slack history (customer-feedback only):**
> Clear `nightly-results/customer-feedback/last-run.json` to `{}` before 07:30 Friday

**Disable a job temporarily:**
> "Disable paycontrol-weekly-summary"

**Preview the report without posting to Slack:**
> "Dry run paycontrol-weekly-summary — do not post to Slack"

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Nothing posted to Slack | Webhook URL expired or rotated | Update `config/slack-webhooks.json` |
| Customer feedback shows 0 items | Snapshot `last_ts` is too recent | Clear `last-run.json` to `{}` |
| Board columns missing from report | GitHub token lacks `read:project` scope | Add scope to the token |
| Job shows `already-running` | Previous run still in progress | Wait — typical runtime is 4–7 min |
| Job failed with Telegram error | Old delivery config present | Set `delivery: {mode: "none"}` on the job |
