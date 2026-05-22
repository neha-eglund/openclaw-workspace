---
name: paycontrol-weekly-summary
description: "Generates a weekly engineering dashboard for PayControlLimited/PayControl, PayControlLimited/PayControl-PCI, and PayControlLimited/PayControl-GitOps covering the rolling last 7 days. Cross-repo snapshot header with per-repo mini cards, posted to webchat + Slack #paycontrol-reports."
---

# PayControl Weekly Summary

Repositories: `PayControlLimited/PayControl`, `PayControlLimited/PayControl-PCI`, `PayControlLimited/PayControl-GitOps`
Window: rolling last 7 days, ending now
Output: cross-repo dashboard + per-repo mini cards, posted to webchat and Slack

---

## Usage

```bash
export GH_TOKEN=ghp_...
export DRY_RUN=true

# Claude
claude -p "Read this SKILL.md and execute all instructions in it exactly as written."

# Codex
codex "Read this SKILL.md and execute all instructions in it exactly as written."
```

---

## Workflow

### Step 1 — Set credentials

```bash
export GH_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/openclaw.json'))['env']['vars']['GH_TOKEN'])")
export REPORTS_CHANNEL_ID=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json'))['paycontrol_reports_channel'])")
# Optional: export DRY_RUN=true  — set this to skip Slack posting and print to stdout only
```

### Step 2 — Fetch all data

```bash
python3 ~/.openclaw/workspace/skills/paycontrol-weekly-summary/scripts/fetch_data.py
```

Reads: GitHub project board + issues, PRs, direct commits for all 3 repos.
Writes: `/tmp/ws_board.json`, `/tmp/ws_window.json`, `/tmp/ws_*_<repo>.json`

### Step 3 — Analyse per-repo impact signals

Read the fetched data and derive three impact lines per repo. This is agent reasoning — not code.

**▲ Shipped impact** — What can users or operators do now that they couldn't before? Read PR body "Summary" sections and linked issue titles. Write 1–2 sentences. Append issue/PR numbers in parentheses. Use issue number if the PR references one; fall back to PR number if untracked. Priority: user-facing feature > security fix > reliability > infra simplification > devx.

**▼ Risk delta** — What risk opened or closed this week? Count:
- Security issues newly opened vs closed (net change)
- SEC_CRITICAL: open security issues >90 days (🔴)
- SEC_SLA: open security issues >13 days (🟡)
- Any reverts or new high-severity bugs
Write 1 sentence. Append the most critical issue numbers e.g. "(#598, #599 — 134d)".

**→ System change** — Structural change affecting operations, scaling, or maintenance. 1 sentence or omit.

**Untracked work detection:**
- PRs without an issue: merged PRs with no `#NNN` reference in title+body → flag as `(PR#N — no issue)`
- Direct commits: already identified by `fetch_data.py` in `/tmp/ws_direct_commits_*.json` — show as `⚡ Direct commits` if any exist

**Stale column detection** (from `/tmp/ws_board.json`):
- In Progress > 14 days → stale
- Review > 7 days → stale
Show as `⏳ Stale on board` under the relevant repo section.

**Risk rubric for action items (rank order):**
1. 🔴 Security issues open >90 days
2. 🔴 Security SLA breaches (>13 days), unassigned
3. 🟡 Net security risk grew (more opened than closed)
4. 🟡 Bus-factor: one contributor >40% of merged PRs
5. 🟡 Stale PR open >30 days with no reviewer
6. 🟡 Direct commits to main
7. 🟡 Revert events
8. 🟡 Frozen backlog (>80% of open issues stale >14d)

After analysis, compute these stats and write `/tmp/ws_stats.json`:
```json
{
  "paycontrol": { "open_issues": N, "merged_prs": N, "sec_open": N, "sec_critical": N, "stale_issues": N, "untracked_prs": N },
  "pci":        { "open_issues": N, "merged_prs": N, "sec_open": N, "sec_critical": N, "stale_issues": N, "untracked_prs": N },
  "gitops":     { "merged_prs": N, "untracked_prs": N, "direct_commits_human": N }
}
```

### Step 4 — Save snapshot and compute deltas

```bash
python3 ~/.openclaw/workspace/skills/paycontrol-weekly-summary/scripts/snapshot.py
```

Reads: `/tmp/ws_stats.json`, `/tmp/ws_window.json`
Writes: `nightly-results/weekly-summary/snapshot-{today}.json`, `/tmp/ws_deltas.json`

### Step 5 — Resolve contributor full names (mandatory)

Before generating any report output, resolve every GitHub login to a full name.

```python
import json
names = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/contributor-names.json'))
```

For any login not in the cache, fall back to the GitHub API and add it:
```bash
gh api /users/<login> --jq '.name'
```

Use only full names everywhere — never show a login or @handle.

### Step 6 — Post to webchat

Output the full report using the webchat template below.

### Step 7 — Build report and post to Slack

Build the four messages, write them to `/tmp/ws_report.json`:
```json
{
  "main_message":   "...",
  "thread_reply_1": "...",
  "thread_reply_2": "...",
  "thread_reply_3": "...",
  "thread_reply_4": "..."
}
```

Then post:
```bash
DRY_RUN_FLAG=""
[ "${DRY_RUN}" = "true" ] && DRY_RUN_FLAG="--dry-run"
python3 ~/.openclaw/workspace/skills/paycontrol-weekly-summary/scripts/post_slack.py $DRY_RUN_FLAG
```

If `DRY_RUN=true`, the script prints all messages to stdout and exits without posting to Slack.

### Step 8 — Done

Print: `Delivered weekly dashboard for 3 repos (PayControl: N PRs, PCI: N PRs, GitOps: N PRs) — posted to webchat and Slack #paycontrol-reports.`

---

## Report Templates

### Webchat

```
# PayControl Engineering — Weekly Dashboard · <Mon Day>–<Day>, <Year>

## Cross-Repo Snapshot

| Repo | Open issues | Merged PRs | Security open (delta) |
|---|---|---|---|
| PayControl        | <N> | <N> | <N> (+<N> this week) |
| PayControl-PCI    | <N> | <N> | <N> (no change)      |
| PayControl-GitOps | <N> | <N> | —                    |

---

## PayControl

▲ <Shipped impact — named capabilities with linked issues/PRs.>
▼ <Risk delta — net direction, critical items named.>
→ <System change or omit.>

_Building: <in-flight> (#N, #N)_

⏳ Stale on board:
  • #N <title> — <Column>, <N>d — <assignee or unassigned>

⚡ Direct commits (<N> human):
  • `sha` <message> — <author>

---

## PayControl-PCI

▲ ...  ▼ ...  → ...
_Building: ..._
⏳ ...

---

## PayControl-GitOps

▲ ...  ▼ ...  → ...
⚡ ...

---

## Week-over-Week · <prev date> → <this date>

| | PayControl | PayControl-PCI | PayControl-GitOps |
|---|---|---|---|
| Issues open    | <N> (<delta>) | ... | — |
| PRs merged     | <N> (<delta>) | ... | <N> (<delta>) |
| Security open  | <N> (<delta 🔴/✅>) | ... | — |
| Stale issues   | <N> (<delta>) | ... | — |
| Untracked PRs  | <N> (<delta>) | ... | <N> (<delta>) |

---

## Action Items

• 🔴 <title> — <detail> (#N)
• 🟡 [<Repo>] <title> — <detail> (#N)
(Up to 5, ranked by severity.)

---

## By Contributor

| Contributor | PRs | Repos |
|---|---|---|
| <Name> | <N> (+ <N> direct) | <repos> |
(Human authors only, ranked by total PRs.)
```

### Slack — Main message

Use Slack mrkdwn: `*bold*`, `_italic_`, `<url|text>` links, `•` bullets. No `#` headers, no `---`, no pipe tables.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 *PayControl Engineering · {date_from}–{date_to}*
{N} PRs merged · {I} issues closed · {C} contributors · {S} security open

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ *TEAM SPOTLIGHTS*
• Full Name — issues closed · PRs merged · one short impact sentence

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 *KEY DELIVERIES*
*── PayControl ──*
• emoji *Bold title* — description. Full Name · <url|Issue #NNN> · <url|PR #NNN>
*── PayControl-PCI ──*  ...
*── PayControl-GitOps ──*  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 *NEEDS ATTENTION*
Only 🔴 items. Omit section entirely if none.

_Full stale list, contributor stats, and trends in thread 👇_
```

### Slack — Thread reply 1 (Week-over-week)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*[ ~ ]  Week-over-Week · <prev date> → <this date>*
• *PayControl*        issues <N> (<delta>)  · merged <N> (<delta>)  · sec <N> (<delta 🔴/✅>)
• *PayControl-PCI*    issues <N> (<delta>)  · merged <N> (<delta>)  · sec <N> (<delta>)
• *PayControl-GitOps* merged <N> (<delta>)  · untracked <N> (<delta>)
```

### Slack — Thread reply 2 (Stale + Action items + Contributors)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*⏳ Stale items*
• <url|#N> <title> — <Column>, <N>d — _<assignee>_  (🔴 >30d · 🟠 >14d · 🟡 >7d)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*[ ! ]  Action Items*
• *🔴 <title>* — <detail>: <url|#N>
• *🟡 [Repo] <title>* — <detail>: <url|#N>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*[ + ]  By Contributor*
• <Name>  *<N> PRs* _(+ <N> direct)_  — _<repos>_
```

### Slack — Thread reply 3 (Board flow)

Heading: `*📋 Board flow — PayControlLimited/projects/1*`

Sections in order:
- *✅ Done this week* — issues moved to Done column
- *🔥 P0 in flight* — P0 items in In Progress / Review / Test
- *⏳ Stale in flight (>14 days)* — In Progress / Review / Test only (not Todo)
- *👀 In Review >3 days* — list with age + pipe-link
- *⏱ Cycle time* — plain English: "Most PRs shipped in Xd · slowest 10% took Y+ days"
- *🕐 Time to first review* — plain English: "Most got a review within Xh · X PRs waited >24h"
- *👤 WIP per person* — flag anyone with >2 items in flight
- *📊 Throughput trend* — PRs merged per week, last 4 weeks
- *💡 Recommendations* — exactly 2 bullets, grounded in this week's data only

### Slack — Thread reply 4 (PR tracking)

Heading: `*🔗 PR tracking — this week's merged PRs*`
- *❌ Untracked* — one bullet per merged PR with no linked issue (PR pipe-link + author)
- Per-person table: Name | Tracked | Untracked | Total — sorted by untracked desc
- Summary line: `{T} of {N} PRs this week were linked to an issue.`

---

## Tone guidelines (mandatory)

- **Neutral and factual** — no personal opinions, no judgements about individuals
- **Positive framing** — celebrate what shipped; stale items are opportunities, not failures
- **Stale PRs** — "waiting for review" or "ready for a decision", not "abandoned"
- **Untracked PRs** — nudge to link issues before starting work, not a criticism
- **Security issues** — factual: state age and count; recommend the concrete next step
- **Team spotlights** — always end with a positive impact sentence
- **No external names** — no client names, company names, or personal contacts
