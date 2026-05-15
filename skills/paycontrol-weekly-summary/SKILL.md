---
name: paycontrol-weekly-summary
description: "Generates a weekly engineering dashboard for PayControlLimited/PayControl, PayControlLimited/PayControl-PCI, and PayControlLimited/PayControl-GitOps covering the rolling last 7 days. Cross-repo snapshot header with per-repo mini cards. Produces a chart PNG and posts to webchat + Slack #paycontrol-reports."
---

# PayControl Weekly Summary

Repositories:
- `PayControlLimited/PayControl`
- `PayControlLimited/PayControl-PCI`
- `PayControlLimited/PayControl-GitOps`

Window: rolling last 7 days, ending now
Output: cross-repo dashboard + per-repo mini cards, chart PNG, posted to webchat and Slack

## Workflow

### 1. Set token and compute the window

```bash
export GH_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/openclaw.json'))['env']['vars']['GH_TOKEN'])")
SINCE=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ)
TODAY=$(date +%Y-%m-%d)
SINCE_DATE=$(date -u -v-7d +%Y-%m-%d)
echo "Window: $SINCE_DATE -> $TODAY"
```

### 2. Pull GitHub project board state

Query `PayControlLimited/projects/1` for in-progress and review items. Required for the mini card "In flight" line.

```bash
gh api graphql -f query='
{
  organization(login: "PayControlLimited") {
    projectV2(number: 1) {
      items(first: 100) {
        nodes {
          content {
            ... on Issue  { number title state }
            ... on PullRequest { number title state }
          }
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
        }
      }
    }
  }
}'
```

Group items by Status into: **In Progress / Review**, **Todo / Backlog**, **Done / Shipped**.

If `read:project` scope is missing, skip and note unavailable.

### 3. Pull repository data (run all three repos in parallel)

Run the same query block for each repo, substituting the repo name:

```bash
REPOS=(PayControlLimited/PayControl PayControlLimited/PayControl-PCI PayControlLimited/PayControl-GitOps)

for REPO in "${REPOS[@]}"; do
  # Issues closed this week
  gh issue list --repo $REPO --state closed --limit 100 \
    --search "closed:>=$SINCE_DATE" \
    --json number,title,closedAt,author,labels &

  # All open issues (stale detection + security scan)
  gh issue list --repo $REPO --state open --limit 200 \
    --json number,title,createdAt,updatedAt,assignees,labels &

  # PRs merged this week
  gh pr list --repo $REPO --state merged --limit 100 \
    --search "merged:>=$SINCE_DATE" \
    --json number,title,createdAt,mergedAt,author,labels,additions,deletions,body &

  # Open PRs
  gh pr list --repo $REPO --state open --limit 100 \
    --json number,title,createdAt,author,labels,body &
done
wait
```

### 4. Compute per-repo impact signals

For each repo, derive three impact lines by reading PR bodies/summaries and issue titles — not counting activity, but describing what changed for users, operators, or the system.

**▲ Shipped impact** — What can users or operators do now that they couldn't before? Read PR body "Summary" sections and linked issue titles. Write 1–2 sentences. After each capability, append the issue or PR number(s) that delivered it in parentheses — e.g. "(#1593, #1596)". Use the issue number if the PR references one; fall back to PR number if untracked. Prioritise: user-facing feature > security fix > reliability improvement > infra simplification > devx.

**▼ Risk delta** — What risk opened or closed this week? Count:
- Security issues newly opened vs closed (net change)
- SEC_CRITICAL: open security issues >90 days (🔴)
- SEC_SLA: open security issues >13 days (🟡)
- Any reverts (signal of instability)
- New high-severity bugs opened
Write 1 sentence. Append the most critical issue numbers in parentheses — e.g. "(#598, #599 — 134d)".

**→ System change** — What structural change landed that affects how the system is operated, scaled, or maintained? E.g. infrastructure migrations, dependency upgrades, schema changes, removal of legacy components. Append the issue or PR number(s). 1 sentence or omit if nothing significant.

**Untracked work detection** — surface work that happened outside the normal PR→issue flow:

- **PRs without an issue**: merged PRs where title+body contain no `#\d{3,}` reference. List them in the ▲ line with `(PR#N — no issue)` so they are visible but clearly flagged as untracked.
- **Direct commits without a PR**: query commits to main with `parents.length == 1` (not a merge commit). For each, note sha, message, author, date. If any exist, add a `⚡ Direct commits` line under the mini card — these bypassed both issue and PR flow entirely.

```bash
gh api "/repos/$REPO/commits?sha=main&since=${SINCE}&per_page=100" \
  --jq '[.[] | select(.parents | length == 1) | {sha: .sha[0:7], message: (.commit.message | split("\n")[0]), author: .commit.author.name, date: .commit.author.date}]'
```

**Stale column detection** — surface issues stuck in a board column abnormally long:

From the project board data (step 2), for each item in **In Progress** or **Review**, compute days since `updatedAt`. Flag as stale if:
- In Progress > 14 days with no `updatedAt` activity
- Review > 7 days with no `updatedAt` activity

Add a `⏳ Stale on board` line under the relevant repo mini card listing each stuck item with its column and age. This catches issues the board shows as active but that haven't moved.

```
⏳ Stale on board:
  • #N <title> — In Progress, <N>d — <assignee or unassigned>
  • #N <title> — Review, <N>d — <assignee>
```

Also compute for snapshot table:
- `OPEN` — total open issues
- `MERGED` — PRs merged in window
- `SEC_OPEN` — total open security issues
- `SEC_DELTA` — security issues opened minus closed this week (+ means risk grew)

**Risk rubric for action items (rank order):**
1. 🔴 Security issues open >90 days
2. 🔴 Security SLA breaches (>13 days), unassigned
3. 🟡 Net security risk grew this week (more opened than closed)
4. 🟡 Bus-factor: one contributor >40% of merged PRs
5. 🟡 Stale PR open >30 days with no reviewer
6. 🟡 Direct commits to main (bypassed PR flow)
7. 🟡 Revert events (process signal)
8. 🟡 Frozen backlog (>80% of open issues stale >14d)

### 5. Load last week's snapshot and compute trend

Load the most recent previous snapshot (if any) to compute week-over-week deltas.

```python
import json, os, glob
from datetime import datetime, timezone

OUT_DIR = os.path.expanduser("~/.openclaw/workspace/nightly-results/weekly-summary")
os.makedirs(OUT_DIR, exist_ok=True)

# Find last week's snapshot (most recent JSON before today)
snapshots = sorted(glob.glob(f"{OUT_DIR}/snapshot-*.json"))
last_snapshot = json.load(open(snapshots[-1])) if snapshots else None

# Build this week's snapshot from computed stats
this_snapshot = {
    "date": TODAY,
    "paycontrol": {
        "open_issues": OPEN_PC,
        "merged_prs": MERGED_PC,
        "sec_open": SEC_OPEN_PC,
        "sec_critical": SEC_CRITICAL_PC,
        "stale_issues": STALE_PC,
        "untracked_prs": UNTRACKED_PC
    },
    "pci": {
        "open_issues": OPEN_PCI,
        "merged_prs": MERGED_PCI,
        "sec_open": SEC_OPEN_PCI,
        "sec_critical": SEC_CRITICAL_PCI,
        "stale_issues": STALE_PCI,
        "untracked_prs": UNTRACKED_PCI
    },
    "gitops": {
        "merged_prs": MERGED_GO,
        "untracked_prs": UNTRACKED_GO,
        "direct_commits_human": DIRECT_HUMAN_GO
    }
}

# Save this week's snapshot
with open(f"{OUT_DIR}/snapshot-{TODAY}.json", "w") as f:
    json.dump(this_snapshot, f, indent=2)
```

**Compute deltas** — for each metric, delta = this week - last week. Format as:
- Positive number: `+N ↑` — use 🔴 if it's a bad signal (sec_open, stale, untracked), ✅ if good (merged_prs)
- Negative number: `-N ↓` — use ✅ if it's a good signal (sec_open, stale going down), 🔴 if bad (merged_prs dropping sharply)
- Zero: `no change`
- No previous snapshot: `(no prior data)`

### 6. Generate the chart

Chart covers `PayControlLimited/PayControl` only (main repo), using the same parameters as before.

```bash
SKILL_DIR="$HOME/.openclaw/workspace/skills/paycontrol-weekly-summary"
OUT_DIR="$HOME/.openclaw/workspace/nightly-results/weekly-summary"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/paycontrol-weekly-$TODAY.png"

python3 "$SKILL_DIR/chart.py" "$OUT" "$TODAY" \
  <OPEN> <TTM_MEDIAN> \
  '<issues_by_area_json>' \
  '[<u1>,<14>,<424>,<13d>,<o3d>]'
```

If matplotlib is missing: `pip3 install --quiet --user matplotlib`.

### 6. Post to webchat

Output `MEDIA:<chart path>` first, then the report in markdown format using the template below.

### 7. Resolve contributor full names (mandatory)

For every GitHub login that appears in the report, resolve it to the contributor's full name:

```bash
gh api /users/<login> --jq '.name'
```

Use only the full name everywhere in the report — Team Spotlights, Key Deliveries, Contributors list, stale PR assignees, and action items. Do NOT show the login or @handle.

### 8. Post to Slack — 4 messages (60 seconds apart)

Post FOUR messages to #paycontrol-reports. Schedule each with a 60-second background sleep:

```bash
(sleep 60 && python3 /tmp/post_msg2.py) &
(sleep 120 && python3 /tmp/post_msg3.py) &
(sleep 180 && python3 /tmp/post_msg4.py) &
```

**Message 1 (immediate)** — Header snapshot:
- 🚀 *PayControl Engineering — [date range]*
- Totals line: PRs merged · issues closed · contributors
- Repo stats in triple-backtick code block: Repo | PRs | Issues Closed | In Progress | In Review | Security

**Message 2 (+60s)** — Team spotlights + key deliveries:
```
━━━━━━━━━━━━━━━━━━━━━━
⭐ *TEAM SPOTLIGHTS*
One bullet per contributor: *Full Name* + issues closed (only if >0, before PRs) + PRs merged + one short impact sentence.

━━━━━━━━━━━━━━━━━━━━━━
🔑 *KEY DELIVERIES*
*── PayControl ──*  *── PayControl-PCI ──*  *── PayControl-GitOps ──*
Each: emoji + *Bold title* — max 5-6 words. Full Name · <url|Issue #NNN> · <url|PR #NNN>
```

**Message 3 (+120s)** — Stale items:
- Stale board issues (🔴 >30d, 🟡 >7d): pipe-link + age + column + full name assignee + nudge
- Stale PRs: pipe-link + age + action needed
- One-line untracked PR nudge

**Message 4 (+180s)** — Action items + contributors:
- Action items: priority emoji + pipe-links + description + bold age
- Contributors: *Full Name* + PRs + issues closed + repos
- Total line

Load webhook:
```python
import json, urllib.request
webhook = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-webhooks.json'))['paycontrol-reports']
```

---

## Report Templates

### Webchat

Produce exactly this structure. Omit ⏳ and ⚡ lines if empty for that repo.

```
MEDIA:<chart path>

# PayControl Engineering — Weekly Dashboard · <Mon Day>–<Day>, <Year>

## Cross-Repo Snapshot

| Repo | Open issues | Merged PRs | Security open (delta) |
|---|---|---|---|
| PayControl        | <N> | <N> | <N> (+<N> this week) |
| PayControl-PCI    | <N> | <N> | <N> (no change)      |
| PayControl-GitOps | <N> | <N> | —                    |

---

## PayControl

▲ <What users/operators can now do — named capabilities with linked issues/PRs.>
  (#N, #N, PR#N — no issue, PR#N — no issue)

▼ <What risk opened or closed — net direction, critical items named.>
  (#N — <N>d, #N — <N>d)

→ <Structural system change that affects operations/scale. Omit line if nothing significant.>
  (#N, PR#N — no issue)

_Building: <active in-flight work with issue links> (#N, #N, #N)_

⏳ Stale on board:
  • #N <title> — <Column>, <N>d — <assignee or unassigned>
  • #N <title> — <Column>, <N>d — <assignee>

⚡ Direct commits (<N> human — bypassed PR flow):
  • `sha` <message> — <author>
  (+ <N> automated commits — not flagged)

---

## PayControl-PCI

▲ <Shipped impact with issue/PR links.>
  (#N, PR#N)

▼ <Risk delta.> (#N — <N>d)

→ <System change or omit.>

_Building: <in-flight> (#N, PR#N)_

⏳ Stale on board:
  • #N <title> — <Column>, <N>d — <assignee> ⚠️

---

## PayControl-GitOps

▲ <Shipped impact — include untracked PR#N — no issue inline.>
  (PR#N, PR#N, PR#N — no issue)

▼ <Risk delta or "No new risk signals.">

→ <System change.> (PR#N, PR#N)

_Building: <in-flight> (PR#N, closes PayControl#N)_

⚡ Direct commits (<N> human — bypassed PR flow):
  • `sha` <message> — <author>
  (+ <N> automated Flux commits — expected, not flagged)

---

## Week-over-Week · <prev date> → <this date>

| | PayControl | PayControl-PCI | PayControl-GitOps |
|---|---|---|---|
| Issues open    | <N> (<delta>) | <N> (<delta>) | — |
| PRs merged     | <N> (<delta>) | <N> (<delta>) | <N> (<delta>) |
| Security open  | <N> (<delta 🔴/✅>) | <N> (<delta>) | — |
| Stale issues   | <N> (<delta>) | <N> (<delta>) | — |
| Untracked PRs  | <N> (<delta>) | <N> (<delta>) | <N> (<delta>) |

(If no prior snapshot: "No prior data — trend will appear from next week.")

---

## Action Items

• 🔴 <title> — <detail> (#N)
• 🔴 <title> — <detail>
• 🟡 [<Repo>] <title> — <detail> (#N or PR#N)
• 🟡 [<Repo>] <title> — <detail>
• 🟡 <title> — <detail>
(Up to 5, ranked by severity. Prefix repo in brackets if repo-specific.)

---

## By Contributor

| Contributor | PRs | Repos |
|---|---|---|
| <Name> | <N> (+ <N> direct) | <repos> |
| <Name> | <N> | <repos> |
...
(Human authors only, ranked by total PRs. Note direct commits separately.)
```

### Slack — Message 1

Use Slack mrkdwn strictly: `*bold*`, `_italic_`, `<url|text>` links, `•` bullets, no `#` headers, no `---`, no pipe tables.

```
*PayControl Engineering — Weekly Dashboard · <Mon Day>–<Day>, <Year>*

*[ # ]  Snapshot*
• *PayControl*        _<N> open · <N> merged · <N> sec issues (+<N> this week)_
• *PayControl-PCI*    _<N> open · <N> merged · <N> sec issues (no change)_
• *PayControl-GitOps* _<N> merged_

*── PayControl ──*
▲ <shipped impact> _(<url|#N>, <url|#N>, <url|PR#N> — no issue)_
▼ <risk delta> _(<url|#N> — <N>d, <url|#N> — <N>d)_
→ <system change> _(<url|#N>, <url|PR#N> — no issue)_ _(omit line if nothing significant)_
_Building: <in-flight> (<url|#N>, <url|#N>)_
⏳ • <url|#N> <title> — <Column>, <N>d — _<assignee>_
⚡ `sha` <message> — _<author>_  _(+ <N> Flux automated)_

*── PayControl-PCI ──*
▲ <shipped impact> _(<url|#N>, <url|PR#N>)_
▼ <risk delta> _(<url|#N> — <N>d)_
_Building: <in-flight> (<url|#N>, <url|PR#N>)_
⏳ • <url|#N> <title> — <Column>, <N>d ⚠️

*── PayControl-GitOps ──*
▲ <shipped impact> _(<url|PR#N>, <url|PR#N> — no issue)_
▼ <risk delta or "No new risk signals">
→ <system change> _(<url|PR#N>)_
_Building: <in-flight> (<url|PR#N>, closes <url|PayControl#N>)_
⚡ `sha` <message> — _<author>_  _(+ <N> Flux)_
```

### Slack — Message 2

```
*PayControl Weekly · <date>  (2/2)*

*[ ~ ]  Week-over-Week · <prev date> → <this date>*
• *PayControl*        issues <N> (<+/-N ↑↓>)  ·  merged <N> (<+/-N>)  ·  sec <N> (<+/-N 🔴/✅>)  ·  stale <N> (<+/-N>)
• *PayControl-PCI*    issues <N> (<+/-N>)  ·  merged <N> (<+/-N>)  ·  sec <N> (<+/-N>)
• *PayControl-GitOps* merged <N> (<+/-N>)  ·  untracked <N> (<+/-N>)
_(No prior data — trend from next week)_ ← use this line only if no snapshot exists

*[ ! ]  Action Items*
• *🔴 <title>* — <detail>: <url|#N>
• *🔴 <title>* — <detail>
• *🟡 [<Repo>] <title>* — <detail>: <url|#N>
• *🟡 [<Repo>] <title>* — <detail>: <url|PR#N>
• *🟡 <title>* — <detail>
_(Up to 5, ranked by severity.)_

*[ + ]  By Contributor*
• <Name>  *<N> PRs* _(+ <N> direct)_  — _<repos>_
• <Name>  *<N> PRs*  — _<repos>_
_(Human authors only, ranked by total PRs.)_
```

### 8. Done

Print: "Delivered weekly dashboard for 3 repos (PayControl: N PRs, PCI: N PRs, GitOps: N PRs) — posted to webchat and Slack #paycontrol-reports (2 messages)."
