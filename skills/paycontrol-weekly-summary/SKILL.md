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

### 6. Resolve contributor full names (mandatory)

Before generating any report output, resolve every GitHub login that appears in the data to the contributor's full name.

Load the names cache first:

```python
import json
names = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/contributor-names.json'))
# names is a dict: {"alipas": "Apostolis Lipas", ...}
```

For any login not in the cache, fall back to the GitHub API and add it to the file:

```bash
gh api /users/<login> --jq '.name'
```

Use only the full name everywhere in the report — Team Spotlights, Key Deliveries, Contributors list, stale PR assignees, and action items. Do NOT show the login or @handle anywhere (webchat or Slack).

### 7. Post to webchat

Output `MEDIA:<chart path>` first, then the report in markdown format using the template below.

### 8. Post to Slack — 1 main message + 3 thread replies

Post a short summary to the channel, then reply in the thread with full detail. Use `chat.postMessage` with the bot token — do NOT use the webhook (webhooks cannot post to threads).

```python
import json, urllib.request

config = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json'))
token = config['bot_token']
# Set DRY_RUN = True to skip Slack posting entirely — output appears in webchat only
DRY_RUN = False
channel = config['paycontrol_reports_channel']

if DRY_RUN:
    print("DRY RUN — Slack posting skipped. Full report output above in webchat.")
    raise SystemExit(0)

def post(text, thread_ts=None):
    payload = {'channel': channel, 'text': text}
    if thread_ts:
        payload['thread_ts'] = thread_ts
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        'https://slack.com/api/chat.postMessage',
        data=data,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    if not resp.get('ok'):
        raise Exception(f"Slack error: {resp.get('error')}")
    return resp['ts']

ts = post(main_message)
post(thread_reply_1, thread_ts=ts)  # week-over-week
post(thread_reply_2, thread_ts=ts)  # stale + action items + contributors
post(thread_reply_3, thread_ts=ts)  # board flow
post(thread_reply_4, thread_ts=ts)  # PR tracking
post(thread_reply_5, thread_ts=ts)  # poll
```

**Main message** — what shipped, who delivered it, what needs attention today:
```
🚀 *PayControl Engineering · {date_from}–{date_to}*
{N} PRs merged · {I} issues closed · {C} contributors · {S} security open

⭐ *TEAM SPOTLIGHTS*
• Full Name — issues closed (only if >0) · PRs merged · one short impact sentence
(one bullet per contributor, ordered by impact)

🔑 *KEY DELIVERIES*
*── PayControl ──*
• emoji *Bold title* — 5-6 word description. Full Name · <url|Issue #NNN> · <url|PR #NNN>
*── PayControl-PCI ──*
• ...
*── PayControl-GitOps ──*
• ...

🚨 *NEEDS ATTENTION*
Only 🔴 items: security issues older than 30 days, PRs open longer than 30 days needing a decision.
One bullet per item. Omit this section entirely if there are no 🔴 items.

_Full stale list, contributor stats, and trends in thread 👇_
```

**Thread reply 1** — Week-over-week snapshot:
- Trend table comparing this week vs last week
- Any notable changes called out in one line
- Last week's poll results (Q1–3) if a previous poll exists; omit section if no prior data

**Thread reply 2** — Stale items + action items + contributors:
- All stale board issues (🔴 >30d, 🟡 >7d): pipe-link + age + column + assignee
- All stale PRs (🔴 >30d, 🟠 >14d, 🟡 >7d): pipe-link + age + action needed
- Untracked PR nudge
- Full action items list: all priorities (🔴 🟠 🟡) with pipe-links + description
- Contributors table: *Full Name* + PRs (tracked/untracked) + issues closed + repos
- Total line

**Thread reply 3** — Board flow:
Heading: *📋 Board flow — PayControlLimited/projects/1*
Sections in order:
- *✅ Done this week* — issues moved to Done column this week (number, title, pipe-link)
- *🔥 P0 in flight* — P0 items currently in In Progress / Review / Test
- *⏳ Stale in flight (>14 days)* — In Progress / Review / Test items only (not Todo); list with age + column
- *👀 In Review >3 days* — list each item with age, pipe-link, nudge to action
- *⏱ Cycle time (PR open → merge, this week)* — write as plain English: "Most PRs shipped in Xd · slowest 10% took Y+ days". Name the slowest PR and why it was larger.
- *🕐 Time to first review* — write as plain English: "Most PRs got a first review within Xh · X PRs waited more than 24h". Name the PRs that waited longest.
- *👤 WIP per person* — items currently In Progress / Review / Test per person. Write as a simple list. Flag anyone with >2 in plain language: "X has Y things in flight at once — risk of context switching".
- *📊 Throughput trend* — PRs merged per week, last 4 weeks with a bar chart. Do not add narrative here — the numbers feed into the Recommendations section.
- *🔀 Stage transition times* — compute avg time in each active column using `updatedAt` as proxy. Do not add narrative here — feed into Recommendations.
- *💡 Recommendations* — exactly 2 bullets, grounded in the stale/review data from this week only. Format: `• [action verb] [specific pipe-linked item] — [reason in one clause]`. No generic advice.

**Thread reply 4** — Tracked vs untracked PRs:
Heading: *🔗 PR tracking — this week's merged PRs*
Two sections:
- *❌ Untracked* — merged PRs with no linked issue (show PR pipe-link + author), one bullet per PR
- A per-person table: Name | Tracked | Untracked | Total — sorted by untracked desc
Then a one-line summary: `{T} of {N} PRs this week were linked to an issue.`

**Thread reply 5** — Feedback poll:
Post the poll intro then 4 questions (reactions pre-added to Q1–3, Q4 is free text):
```
📊 *Quick feedback on this week's report — takes 10 seconds 👆 React with the number that matches your answer*

*1. Did the report correctly capture what the team shipped this week?*
1️⃣  Yes, accurate   2️⃣  Some gaps   3️⃣  Something was missed

*2. Were the action items and priorities right?*
1️⃣  Spot on   2️⃣  Some were wrong   3️⃣  Mostly off

*3. Did the report have good structure?*
1️⃣  Yes, easy to follow   2️⃣  Could be better   3️⃣  Hard to navigate

*4. Anything missing or you'd like to see differently?* Reply in this thread 👇
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

### 8. Tone guidelines (mandatory)

Apply these rules to every section of both the webchat and Slack output:

- **Neutral and factual** — no personal opinions, no judgements about individuals or their work
- **Positive framing** — celebrate what shipped; frame stale items and action items as opportunities to move things forward, not as failures
- **Stale PRs** — describe as "waiting for review" or "ready for a decision", not "abandoned" or "neglected"
- **Untracked PRs** — frame as a nudge to link issues before starting work, not a criticism
- **Security issues** — factual: state age and count; recommend the concrete next step (e.g. "ready to merge", "needs triage")
- **Team spotlights** — always end with a positive impact sentence; never omit a contributor who shipped something
- **No external names** — do not mention client names, company names, or personal contacts from outside the team

### 9. Read last week's poll results and post new poll

#### 9a — Read last week's poll reactions

Load the most recent poll file:

```python
import json, glob, urllib.request, os

POLL_DIR = os.path.expanduser("~/.openclaw/workspace/nightly-results/weekly-summary/polls")
poll_files = sorted(glob.glob(f"{POLL_DIR}/poll-*.json"))
last_poll = json.load(open(poll_files[-1])) if poll_files else None
```

If a previous poll exists, fetch reactions for each question message:

```python
def get_reactions(ts):
    url = f"https://slack.com/api/reactions.get?channel={channel}&timestamp={ts}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    resp = json.loads(urllib.request.urlopen(req).read())
    reactions = resp.get("message", {}).get("reactions", [])
    return {r["name"]: r["count"] - 1 for r in reactions}  # subtract bot's own pre-added reaction

q1_reactions = get_reactions(last_poll["q1_ts"]) if last_poll else None
q2_reactions = get_reactions(last_poll["q2_ts"]) if last_poll else None
q3_reactions = get_reactions(last_poll["q3_ts"]) if last_poll else None
```

Format the results as a thread reply and include it in Thread reply 3 (week-over-week), above the trend table:

```
📊 *Last week's report feedback*
_Did the report help you understand what shipped?_
  1️⃣ {one} · 2️⃣ {two} · 3️⃣ {three}

_Were the flagged action items relevant?_
  1️⃣ {one} · 2️⃣ {two} · 3️⃣ {three}

_Right amount of detail in main message vs thread?_
  1️⃣ {one} · 2️⃣ {two} · 3️⃣ {three}
```

If no previous poll exists, omit this section entirely.

#### 9b — Post this week's poll as a thread reply

Post three separate messages (one per question) as thread replies under the main report message, using the `ts` from the main message. Pre-add reactions so team members just click:

```python
def post_poll_question(text, thread_ts):
    ts = post(text, thread_ts=thread_ts)
    for emoji in ["one", "two", "three"]:
        payload = json.dumps({"channel": channel, "timestamp": ts, "name": emoji}).encode()
        req = urllib.request.Request(
            "https://slack.com/api/reactions.add",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        )
        urllib.request.urlopen(req)
    return ts

# Post poll header first
post("📊 *Quick feedback on this week's report — takes 10 seconds* 👆 React with the number that matches your answer", thread_ts=main_ts)

q1_ts = post_poll_question(
    "*1. Did the report help you understand what the team shipped?*\n1️⃣  Yes, clear picture\n2️⃣  Partially\n3️⃣  Not really",
    thread_ts=main_ts
)
q2_ts = post_poll_question(
    "*2. Were the flagged action items (stale PRs, security) relevant?*\n1️⃣  Yes, all relevant\n2️⃣  Some were off\n3️⃣  Not useful",
    thread_ts=main_ts
)
q3_ts = post_poll_question(
    "*3. Was the right amount of detail in the main message vs thread?*\n1️⃣  Right balance\n2️⃣  More in main message\n3️⃣  Less in main message",
    thread_ts=main_ts
)
```

Save the poll ts values:

```python
os.makedirs(POLL_DIR, exist_ok=True)
json.dump({"date": TODAY, "q1_ts": q1_ts, "q2_ts": q2_ts, "q3_ts": q3_ts},
          open(f"{POLL_DIR}/poll-{TODAY}.json", "w"), indent=2)
```

### 10. Done

Print: "Delivered weekly dashboard for 3 repos (PayControl: N PRs, PCI: N PRs, GitOps: N PRs) — posted to webchat and Slack #paycontrol-reports (2 messages)."
