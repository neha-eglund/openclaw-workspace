---
name: paycontrol-customer-requirements
description: "Reads #paycontrol-feedback Slack channel since last run (or from channel start on first run), cross-references feedback against the GitHub Project board (PayControlLimited/projects/1), classifies each item by Category, Severity, and Status, and posts a structured weekly report to #paycontrol-reports."
---

# PayControl Customer Requirements Report

Slack channel: `#paycontrol-feedback` (ID: `C0AKQRQ6QDA`)
GitHub Project: `PayControlLimited/projects/1`
Output: structured feedback report posted to webchat + Slack `#paycontrol-reports`
Window: since last run (snapshot-driven); first run fetches all messages from channel start

---

## Classification Schema

### Category
- `Bug` — something is broken or behaving incorrectly
- `Compliance` — regulatory or licensing requirement
- `Feature Request` — net-new capability
- `UX` — confusing or inconvenient flow, not broken
- `Integration` — third-party connector or API behavior
- `Analytics` — data visibility, reporting, querying

### Severity
- `🔴 Blocking` — customer can't proceed; escalation or churn risk
- `🟡 High` — significant friction or compliance risk; needs sprint attention
- `🔵 Normal` — improvement, no immediate urgency

### Status
- `✅ Resolved` — fix shipped or confirmed workaround
- `🔧 Tracked` — matched to an open GitHub project item
- `❌ Untracked` — no matching project item found; needs triage

---

## Workflow

### Step 1 — Set credentials

```bash
export SLACK_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json'))['bot_token'])")
export GH_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/openclaw.json'))['env']['vars']['GH_TOKEN'])")
```

### Step 2 — Fetch Slack messages

```bash
python3 ~/.openclaw/workspace/skills/paycontrol-customer-requirements/scripts/fetch_slack.py
```

Writes:
- `/tmp/cf_messages.json` — messages since last run
- `/tmp/cf_threads.json` — thread replies per message
- `/tmp/cf_reaction_resolved.json` — ts list with ✅ reaction
- `/tmp/cf_reaction_acknowledged.json` — ts list with 👍 reaction
- `/tmp/cf_window.json` — `{since_date, today}`

### Step 3 — Fetch GitHub data

```bash
python3 ~/.openclaw/workspace/skills/paycontrol-customer-requirements/scripts/fetch_github.py
```

Writes:
- `/tmp/cf_board.json` — project board items with status column
- `/tmp/cf_all_issues.json` — all issues from all 3 repos (for semantic matching)
- `/tmp/cf_issue_to_prs.json` — issue number → linked PRs

### Step 4 — Handle file attachments

For every Slack message in `/tmp/cf_messages.json` that contains a `files` array:

1. Call `https://slack.com/api/files.info?file=<FILE_ID>` with `$SLACK_TOKEN`
2. Download via `url_private_download` with `-H "Authorization: Bearer $SLACK_TOKEN"`
3. Extract content by type:
   - `.docx` — extract text with `python-docx`
   - `.pdf` — extract text with `pdfplumber` or `pypdf`
   - `.m4a / .mp3 / .wav / .ogg / .webm` — transcribe with Whisper:
     ```bash
     pip3 install --quiet --user openai-whisper
     python3 -c "import whisper; m=whisper.load_model('base'); print(m.transcribe('/tmp/audio')['text'])"
     ```
4. Append extracted content to the message's `full_context`. Add `_Source: voice note (transcribed)_` for audio.

### Step 5 — Read supplement files

Check `/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/supplements/` for `.md` files. Treat each as additional feedback. Move processed files to `supplements/processed/` after the report.

### Step 6 — Classify and match feedback items

Read `/tmp/cf_messages.json` and `/tmp/cf_threads.json`. For each message, build `full_context` = parent text + all thread replies concatenated. Then for each item:

**6a — Classify**
1. Extract a one-line summary of the underlying problem or request
2. Assign Category (Bug / Compliance / Feature Request / UX / Integration / Analytics)
3. Assign Severity (🔴 Blocking / 🟡 High / 🔵 Normal)
4. Note any resolution signals in the thread ("fix is live", "accessible now", "removed")
5. Resolve poster's real name via Slack API:
   ```bash
   curl -s "https://slack.com/api/users.info?user=<USER_ID>" -H "Authorization: Bearer $SLACK_TOKEN"
   ```
   Use `real_name` field. Never show a raw user ID.

**6b — Reaction-based status (check first — highest priority)**

Check `/tmp/cf_reaction_resolved.json` and `/tmp/cf_reaction_acknowledged.json`:
- ✅ on message → `status = ✅ Resolved`, skip GitHub matching
- 👍 on message (and not ✅) → `status = 🔧 Tracked`, still attempt GitHub matching

**6c — GitHub matching**

Check `/tmp/cf_all_issues.json`. Do not keyword-search — read each feedback item semantically and ask: *"Does this issue describe the same underlying problem or feature, even if the words differ?"*

Check thread for explicit GitHub signals first:
```python
import re
github_url_pat = re.compile(r'https://github\.com/PayControlLimited/[^/]+/issues/(\d+)')
bare_ref_pat   = re.compile(r'(?<!\d)#(\d+)(?!\d)')
```

Assign confidence in order:
| Rule | Confidence |
|---|---|
| GitHub URL or confirmed `#NNN` in thread | `definitive` |
| Same problem, same component — clearly the same issue | `high` |
| Same area, plausibly same root cause | `medium` → demote to Untracked |
| Superficial overlap only | `low` → demote to Untracked |

`medium` and `low` → automatically `❌ Untracked` with note `_(possible match: #NNN — verify manually)_`

**6d — Set status for accepted matches**
- CLOSED issue + merged PR → `✅ Resolved`
- OPEN issue → `🔧 Tracked` (note board column from `/tmp/cf_board.json`)
- Thread confirms fix but no issue → `✅ Resolved (confirmed in thread)`

**6e — Collect "worked on by"** (for Resolved and Tracked items only)

Collect contributors from: assignees, issue events, linked PR authors (from `/tmp/cf_issue_to_prs.json`), issue comments. Exclude bots. Resolve logins to full names via `contributor-names.json` then `gh api /users/<login> --jq '.name'`.

**Output:** Build `FEEDBACK_ITEMS` list in memory:
```json
[{
  "summary": "...", "date": "2026-05-10", "category": "UX",
  "severity": "🟡 High", "status": "❌ Untracked",
  "match_confidence": "low",
  "issue_number": null, "issue_url": null, "board_column": null,
  "linked_prs": [], "raised_by": "Name", "worked_on_by": []
}]
```

Write to `/tmp/cf_feedback_items.json`.

### Step 7 — Save snapshot

```bash
python3 ~/.openclaw/workspace/skills/paycontrol-customer-requirements/scripts/save_snapshot.py
```

Reads: `/tmp/cf_feedback_items.json`, `/tmp/cf_window.json`
Writes: cumulative snapshot JSON, updates `last-run.json`, writes `/tmp/cf_deltas.json`

### Step 8 — Build report messages

Build three messages and write to `/tmp/cf_report.json`:
```json
{
  "main_message":   "...",
  "thread_reply_1": "...",
  "thread_reply_2": "..."
}
```

See **Report Format** section below for exact structure of each message.

### Step 9 — Post to Slack

```bash
python3 ~/.openclaw/workspace/skills/paycontrol-customer-requirements/scripts/post_slack.py
# Dry run: python3 .../post_slack.py --dry-run
```

---

## Report Format

### Main message (new items this window only)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 *PayControl · Customer Feedback · {since_date}–{today}*
{N} new items this week · {T} tracked · {U} untracked · {R} resolved

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ *Resolved*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• {emoji} {Category} — {summary}  <url|Issue #N>  · PR #N merged  · _worked on by: Name_  · _match: confidence_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 *Tracked*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• {emoji} {Category} — {summary}  <url|Issue #N>  · {PR links}  · _worked on by: Name_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ *Not tracked — no issue, no PR ({U})*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• {emoji} {Category} — {summary}
  _Question ({date}):_ {neutral description of the gap}
  _Conclusion:_ {recommended next step}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Needs triage*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• No GitHub issue: {list of untracked summaries}
• No PR yet: {list of tracked items without a PR}
```

If no new items: post `_No new feedback this week._`
Omit any section (and its dividers) that has no items.

### Thread reply 1 (week-over-week, cumulative)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Week-over-week · {prev_date} → {today}*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total items  <N>   <delta>
Resolved     <N>   <delta ✅/🔴>
Tracked      <N>   <delta>
Questions    <N>   <delta 🔴/✅>
🔴 Blocking  <N>   <delta>
🟡 High      <N>   <delta>
🔵 Normal    <N>   <delta>
```

### Thread reply 2 (open questions — cumulative, all time)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 *Open questions — possible GitHub matches (manual verification needed)*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• {emoji} {Category} — {summary} · {date}
  → _(possible match: <url|#NNN> STATE — brief overlap note)_   ← only if a possible match exists; omit line entirely otherwise
```

To reconstruct the full historical list, read these sources before composing:
1. `nightly-results/customer-feedback/slack-report-*.txt` — parse all `❌` bullets (severity, category, summary, date)
2. `nightly-results/customer-feedback/supplements/processed/*.md` — items classified as untracked
3. This run's `FEEDBACK_ITEMS` — add new untracked items

Deduplicate by summary. Exclude items resolved or tracked in a later run.

---

## Format rules

- Slack mrkdwn only: `*bold*`, `_italic_`, `<url|label>` links — never raw URLs
- Issue links: `<https://github.com/.../issues/N|Issue #N>`
- PR links: `<https://github.com/.../pull/N|PR #N>`
- Sort within each section: 🔴 → 🟡 → 🔵
- `worked_on_by` empty → show `_worked on by: unassigned_`
- `medium` / `low` confidence → always `❌ Untracked`, never Resolved or Tracked

## Tone rules (mandatory)

- Neutral and factual — describe what was reported, not who said it or how
- No personal opinions, external contact names, or company names from feedback sources
- Untracked items → *areas of improvement* or *opportunities*, not complaints
- _Question_ line: neutral description of the functional gap, not a quote
- _Conclusion_ line: positive recommended next step
- Never use a browser to access Slack — always use the API with `$SLACK_TOKEN`

## Notes

- Feedback channel ID: `C0AKQRQ6QDA` (private, bot is member)
- Reaction-based triage: ✅ = Resolved, 👍 = Tracked. Both override GitHub matching. ✅ takes priority over 👍. Requires `reactions:read` scope.
- False matches are worse than no match — prefer `❌ Untracked` when unsure
- If `read:project` scope is missing, skip Step 3 and mark all items as `❌ Untracked (project unavailable)`
