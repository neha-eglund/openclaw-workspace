---
name: paycontrol-customer-requirements
description: "Reads #paycontrol-feedback Slack channel since last run (or from channel start on first run), cross-references feedback against the GitHub Project board (PayControlLimited/projects/1), classifies each item by Category, Severity, and Status, and posts a structured weekly report to #paycontrol-reports."
---

# PayControl Customer Requirements Report

Slack channel: `#paycontrol-feedback` (ID: `C0AKQRQ6QDA`)
GitHub Project: `PayControlLimited/projects/1`
Output: structured feedback report posted to webchat + Slack `#paycontrol-reports`
Window: since last run (snapshot-driven); first run fetches all messages from channel start
Snapshot file: `/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/last-run.json`

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
- `🔧 Tracked` — matched to an open GitHub project item (show #number + board column)
- `❌ Untracked` — no matching project item found; needs triage

---

## Workflow

### Step 1 — Set credentials and compute window

```bash
SLACK_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json'))['bot_token'])")
WEBHOOK=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-webhooks.json'))['paycontrol-reports'])")
export GH_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/nehaeglund/.openclaw/openclaw.json'))['env']['vars']['GH_TOKEN'])")

mkdir -p /Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback

# Load last-run snapshot — if missing, fetch from channel beginning (oldest=0)
OLDEST=$(python3 -c "
import json, os
path = '/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/last-run.json'
if os.path.exists(path):
    d = json.load(open(path))
    print(d.get('last_ts', '0'))
else:
    print('0')
")

TODAY=$(date +%Y-%m-%d)
echo "Window: will be determined from oldest message fetched  (oldest_ts=$OLDEST)"
```

### Step 2 — Fetch Slack messages from #paycontrol-feedback

```bash
curl -s "https://slack.com/api/conversations.history" \
  -H "Authorization: Bearer $SLACK_TOKEN" \
  -d "channel=C0AKQRQ6QDA" \
  -d "oldest=$OLDEST" \
  -d "limit=200" | python3 -c "
import json, sys
data = json.load(sys.stdin)
msgs = data.get('messages', [])
print(json.dumps(msgs, indent=2))
" > /tmp/feedback_messages.json

python3 -c "
import json, datetime
data = json.load(open('/tmp/feedback_messages.json'))
msgs = data.get('messages', [])
# Derive SINCE_DATE from the oldest message timestamp in the response
if msgs:
    oldest_ts = min(float(m['ts']) for m in msgs)
    since = datetime.datetime.utcfromtimestamp(oldest_ts).strftime('%Y-%m-%d')
else:
    since = '(no messages)'
print(f'Messages fetched: {len(msgs)}  |  Window: {since} -> $(date +%Y-%m-%d)')
# Write SINCE_DATE to a temp file for use in the report
open('/tmp/feedback_since_date.txt','w').write(since)
"
```

For each message, also check for reactions. A ✅ reaction (`white_check_mark`) on a message means the team has manually marked it as resolved — this takes priority over everything else in Step 4:

```bash
python3 -c "
import json
msgs = json.load(open('/tmp/feedback_messages.json'))
resolved_by_reaction = set()
acknowledged_by_reaction = set()
for m in msgs:
    reactions = m.get('reactions', [])
    for r in reactions:
        if r['name'] in ('white_check_mark', 'heavy_check_mark'):
            resolved_by_reaction.add(m['ts'])
        elif r['name'] in ('+1', 'thumbsup'):
            acknowledged_by_reaction.add(m['ts'])
json.dump(list(resolved_by_reaction), open('/tmp/reaction_resolved.json', 'w'))
json.dump(list(acknowledged_by_reaction), open('/tmp/reaction_acknowledged.json', 'w'))
print(f'Resolved by reaction: {len(resolved_by_reaction)}  |  Acknowledged by reaction: {len(acknowledged_by_reaction)}')
"
```

For each message that has `reply_count > 0`, fetch thread replies:

```bash
python3 -c "
import json, subprocess, os
msgs = json.load(open('/tmp/feedback_messages.json'))
token = os.environ['SLACK_TOKEN']
all_threads = {}
for m in msgs:
    if m.get('reply_count', 0) > 0:
        ts = m['ts']
        result = subprocess.run([
            'curl', '-s', 'https://slack.com/api/conversations.replies',
            '-H', f'Authorization: Bearer {token}',
            '-d', 'channel=C0AKQRQ6QDA',
            '-d', f'ts={ts}'
        ], capture_output=True, text=True)
        thread = json.loads(result.stdout).get('messages', [])
        all_threads[ts] = thread[1:]  # skip parent
json.dump(all_threads, open('/tmp/feedback_threads.json', 'w'))
print(f'Threads fetched: {len(all_threads)}')
" SLACK_TOKEN="$SLACK_TOKEN"
```

### Step 3 — Fetch GitHub Project board items

```bash
gh api graphql -f query='
{
  organization(login: "PayControlLimited") {
    projectV2(number: 1) {
      items(first: 200) {
        nodes {
          content {
            ... on Issue {
              number
              title
              state
              url
              body
            }
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
}' > /tmp/project_board.json

python3 -c "
import json
data = json.load(open('/tmp/project_board.json'))
items = data['data']['organization']['projectV2']['items']['nodes']
board = []
for item in items:
    content = item.get('content')
    if not content:
        continue
    status = next(
        (fv['name'] for fv in item['fieldValues']['nodes']
         if fv and fv.get('field', {}).get('name') == 'Status'),
        'Unknown'
    )
    board.append({
        'number': content.get('number'),
        'title': content.get('title', ''),
        'state': content.get('state', ''),
        'url': content.get('url', ''),
        'body': content.get('body', ''),
        'status': status
    })
json.dump(board, open('/tmp/project_items.json', 'w'))
print(f'Project items loaded: {len(board)}')
"
```

### Step 3b — Fetch PRs from all three repos

```bash
for REPO in PayControlLimited/PayControl PayControlLimited/PayControl-PCI PayControlLimited/PayControl-GitOps; do
  REPO_KEY=$(echo $REPO | tr / _)
  gh pr list --repo $REPO --state all --limit 200 \
    --json number,title,body,state,url,closingIssuesReferences 2>/dev/null \
  | python3 -c "
import json, sys
prs = json.load(sys.stdin)
out = []
for pr in prs:
    refs = [i['number'] for i in pr.get('closingIssuesReferences', [])]
    out.append({'number': pr['number'], 'title': pr['title'], 'state': pr['state'],
                'url': pr['url'], 'issue_refs': refs, 'body': (pr.get('body','') or '')[:300]})
json.dump(out, open(f'/tmp/prs_${REPO_KEY}.json','w'))
print(f'{len(out)} PRs from $REPO')
"
done

# Build combined issue→PR index (closingIssuesReferences + body #NNN patterns)
python3 -c "
import json, re
all_prs = []
for repo_key, repo_name in [
    ('PayControlLimited_PayControl','PayControl'),
    ('PayControlLimited_PayControl-PCI','PayControl-PCI'),
    ('PayControlLimited_PayControl-GitOps','PayControl-GitOps')
]:
    prs = json.load(open(f'/tmp/prs_{repo_key}.json'))
    for p in prs:
        p['repo'] = repo_name
        all_prs.append(p)

issue_to_prs = {}
for pr in all_prs:
    for inum in pr['issue_refs']:
        issue_to_prs.setdefault(inum, []).append(pr)
    for ref in re.findall(r'#(\d+)', pr.get('body','')):
        inum = int(ref)
        existing = issue_to_prs.get(inum, [])
        if not any(p['number'] == pr['number'] and p['repo'] == pr['repo'] for p in existing):
            issue_to_prs.setdefault(inum, []).append(pr)

json.dump(issue_to_prs, open('/tmp/issue_to_prs.json','w'))
print(f'PR index built: {len(issue_to_prs)} issues have linked PRs')
"
```

After building the index, also scan PR titles and bodies for `closes/fixes/resolves #NNN` patterns and bare `#NNN` title mentions — add these to the index alongside formal closing references. This catches PRs that close issues without a formal GitHub link.

```python
close_patterns = re.compile(
    r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)',
    re.IGNORECASE
)
for pr in all_prs:
    text = f"{pr['title']} {pr.get('body','') or ''}"
    for m in close_patterns.finditer(text):
        inum = str(int(m.group(1)))
        existing = issue_to_prs.get(inum, [])
        if not any(p['number'] == pr['number'] and p['repo'] == pr['repo'] for p in existing):
            issue_to_prs.setdefault(inum, []).append(pr)
    # bare #NNN in title
    for ref in re.findall(r'(?<!\d)#(\d+)(?!\d)', pr['title']):
        inum = ref
        existing = issue_to_prs.get(inum, [])
        if not any(p['number'] == pr['number'] and p['repo'] == pr['repo'] for p in existing):
            issue_to_prs.setdefault(inum, []).append(pr)
```

In Step 4, for each matched issue, look up its number in `/tmp/issue_to_prs.json` and attach any linked PRs. Show PR number, state (OPEN/MERGED), and repo.

### Step 4 — Classify and match feedback items

Read `/tmp/feedback_messages.json` and `/tmp/feedback_threads.json`. For each Slack message (and its full thread):

#### 4a — Build full thread context

For each message, concatenate the parent message text with all thread replies into a single `full_context` string. This is the primary input for all classification and matching decisions. Do not summarise or truncate at this stage — use the complete text.

#### 4b — Extract and classify

From the `full_context`:

1. **Extract the core feedback** — one-line summary of the underlying problem or request (not how it was phrased — what it means). Include the message date.
2. **Classify Category**: pick from Bug / Compliance / Feature Request / UX / Integration / Analytics
3. **Classify Severity**:
   - 🔴 Blocking — customer cannot proceed, escalation risk, or regulatory obligation
   - 🟡 High — significant friction, compliance risk, or explicitly time-sensitive in the thread
   - 🔵 Normal — improvement, no urgency stated
4. **Note resolution signals in the thread**: if any reply says the fix is shipped, live, "accessible now", "removed", "on the way" and a subsequent message confirms it — note this. It will influence status.
5. **Resolve the poster's real name** — for every Slack message, call:
   ```bash
   curl -s "https://slack.com/api/users.info?user=<USER_ID>" \
     -H "Authorization: Bearer $SLACK_TOKEN"
   ```
   Use the `real_name` field from the response. Always show the real name in the report — never show a raw user ID like `U03NCDJR6`.

#### 4c — GitHub matching (bulk fetch + semantic comparison)

**Do not rely on keyword search.** Instead, fetch all issues from GitHub once, then compare each feedback item semantically against the full issue list. This catches matches even when the terminology differs completely.

**Step 1 — Check thread for definitive GitHub references first**

Before any matching, scan the `full_context` for explicit GitHub signals:

```python
import re
github_url_pat = re.compile(r'https://github\.com/PayControlLimited/[^/]+/issues/(\d+)')
bare_ref_pat = re.compile(r'(?<!\d)#(\d+)(?!\d)')
urls_found = github_url_pat.findall(full_context)
bare_refs = bare_ref_pat.findall(full_context)
```

If a GitHub issue URL is found → **match_confidence = `definitive`** — use that issue number directly, skip all other matching.

If a bare `#NNN` is found → fetch the issue to confirm it relates to the feedback → **match_confidence = `high`** if confirmed.

**Step 2 — Bulk fetch all issues (open + recently closed)**

Run once before processing any feedback items. Fetch all issues from all three repos including both open and closed:

```bash
for REPO in PayControlLimited/PayControl PayControlLimited/PayControl-PCI PayControlLimited/PayControl-GitOps; do
  REPO_KEY=$(echo $REPO | tr / _)
  gh issue list --repo $REPO --state all --limit 500 \
    --json number,title,state,url,body,labels,assignees \
  | python3 -c "
import json, sys
issues = json.load(sys.stdin)
# Trim body to first 400 chars — enough for semantic matching, keeps memory low
for i in issues:
    i['body'] = (i.get('body') or '')[:400]
    i['repo'] = '$REPO'
json.dump(issues, open('/tmp/issues_${REPO_KEY}.json', 'w'))
print(f'{len(issues)} issues from $REPO')
"
done

# Merge into one flat list
python3 -c "
import json
all_issues = []
for repo_key in [
    'PayControlLimited_PayControl',
    'PayControlLimited_PayControl-PCI',
    'PayControlLimited_PayControl-GitOps'
]:
    all_issues.extend(json.load(open(f'/tmp/issues_{repo_key}.json')))
json.dump(all_issues, open('/tmp/all_issues.json', 'w'))
print(f'Total issues loaded: {len(all_issues)}')
"
```

**Step 3 — Semantic comparison per feedback item**

For each feedback item, read its `full_context` and compare it against `/tmp/all_issues.json`. You are doing this comparison — not a keyword search. Ask yourself:

> *"Does this issue describe the same underlying problem or feature as the feedback, even if the words are different?"*

For each issue, consider:
- Does the **title** describe the same functional area or problem type?
- Does the **body** mention the same component, flow, error, or behaviour?
- Is this a **different angle on the same root cause** (e.g. feedback says "button greyed out", issue says "edit state disables all fields")?

Assign confidence using these rules **in order** — use the first that fires:

| Rule | Confidence |
|---|---|
| GitHub URL or confirmed `#NNN` found in Slack thread | `definitive` |
| Same problem, same component — title + body clearly describe the same issue | `high` |
| Same functional area, plausibly the same root cause, body partially matches | `medium` (demoted) |
| Superficial overlap only — different feature or different failure mode | `low` (demoted) |

**Step 4 — Apply confidence gate**

- `definitive` or `high` → use the match; set status as Resolved/Tracked
- `medium` or `low` → **automatically demote to `❌ Untracked`**; note: `_(possible match: #NNN — verify manually)_`
- No match found → `❌ Untracked`

A wrong match is worse than no match — stay conservative.

**Step 5b — Apply reaction-based resolution (highest priority)**

Before any GitHub matching, check the message timestamp against both reaction files.

If the timestamp is in `/tmp/reaction_resolved.json` (✅ reaction):
- Set `status = ✅ Resolved`
- Set `match_confidence = definitive`
- Set `resolution_source = "✅ reaction by team"`
- Skip GitHub matching for this item entirely

If the timestamp is in `/tmp/reaction_acknowledged.json` (👍 reaction) and NOT in the resolved set:
- Set `status = 🔧 Tracked`
- Set `match_confidence = definitive`
- Set `resolution_source = "👍 acknowledged by team"`
- Still attempt GitHub matching to attach an issue/PR if one exists, but the Tracked status is confirmed regardless

✅ takes priority over 👍 if both reactions are present. Both take priority over all other status signals.

**Step 6 — Set status (for accepted matches only)**

- CLOSED issue + merged PR: `✅ Resolved`
- CLOSED issue, no PR: `✅ Resolved` (note reason if visible in issue)
- Thread confirms fix ("accessible now", "removed", "it's fixed") without an issue: `✅ Resolved (confirmed in thread)` — confidence = `definitive`
- OPEN issue: `🔧 Tracked` — note board column from `/tmp/project_items.json` if present

#### 4d — Fetch "worked on by" for matched issues

For each matched issue, collect everyone who touched it across four signals:

**1. Current assignees**
```bash
gh issue view <number> --repo PayControlLimited/PayControl \
  --json assignees | python3 -c "
import json, sys
d = json.load(sys.stdin)
print([a['login'] for a in d.get('assignees', [])])
"
```

**2. Past assignees + activity actors from issue events**
```bash
gh api repos/PayControlLimited/PayControl/issues/<number>/events \
  --paginate | python3 -c "
import json, sys
events = json.load(sys.stdin)
actors = set()
for e in events:
    if e.get('event') in ('assigned', 'unassigned', 'referenced', 'closed', 'mentioned', 'reviewed'):
        actor = (e.get('actor') or {}).get('login')
        assignee = (e.get('assignee') or {}).get('login')
        if actor: actors.add(actor)
        if assignee: actors.add(assignee)
print(sorted(actors))
"
```

**3. PR authors and committers from linked PRs**

For each PR in `/tmp/issue_to_prs.json` linked to this issue:
```bash
gh pr view <pr_number> --repo PayControlLimited/<repo> \
  --json author,commits | python3 -c "
import json, sys
d = json.load(sys.stdin)
people = set()
author = (d.get('author') or {}).get('login')
if author: people.add(author)
for c in d.get('commits', []):
    login = (c.get('authors') or [{}])[0].get('login')
    if login: people.add(login)
print(sorted(people))
"
```

**4. Issue comments authors**
```bash
gh api repos/PayControlLimited/PayControl/issues/<number>/comments | python3 -c "
import json, sys
comments = json.load(sys.stdin)
print(sorted(set((c.get('user') or {}).get('login','') for c in comments if c.get('user'))))
"
```

Merge all four sets into a single deduplicated `worked_on_by` list. Exclude bot accounts (logins ending in `[bot]`).

Then resolve each login to a full name before storing. Load the names cache first:

```python
import json
names = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/contributor-names.json'))
```

For any login not in the cache, fall back to the GitHub API and add it to the file:

```bash
gh api /users/<login> --jq '.name'
```

Store full names (e.g. "Rasmus Middendorff"), not logins. If the API returns null or empty, fall back to the login as-is.

Also check `/tmp/issue_to_prs.json` to attach linked PRs (number, state, repo, url).

Produce a structured list stored in memory as `FEEDBACK_ITEMS`. Each item must include a `match_confidence` field. Medium and low confidence matches are automatically demoted to `❌ Untracked` — they never appear in Resolved or Tracked sections.

```
[
  {
    summary: "one-line title",
    quote: "original Slack message text, trimmed to ~300 chars",
    date: "2026-03-10",
    category: "Bug",
    severity: "🔴 Blocking",
    status: "🔧 Tracked",
    match_confidence: "high",        // definitive / high / medium (demoted) / low (demoted)
    search_phrases_used: ["flow tab decisions demo merchant", "demo merchant decisions missing"],
    issue_number: 142,
    issue_url: "https://github.com/...",
    board_column: "In Progress",
    linked_prs: [{"number": 99, "state": "MERGED", "repo": "PayControl", "url": "..."}],
    raised_by: "Erik",
    worked_on_by: ["Rasmus Middendorff", "Sebastian Andersson"]   // full names from contributor-names.json or gh api /users/<login>; [] if nobody found
  },
  ...
]
```

### Step 5 — Build the report

Group `FEEDBACK_ITEMS` by Category. Within each group, sort by Severity (Blocking → High → Normal). Surface `❌ Untracked` items at the top of each group.

**Webchat and Slack report format — grouped by status then severity:**

```
*PayControl · Customer Feedback · {SINCE_DATE}–{TODAY}*
{N} items · {T} tracked · {U} untracked · {R} resolved

*✅ Resolved*
• {severity_emoji} {Category} — {summary}  {issue_url}  · PR #{n} merged  · _worked on by: {logins}_  · _match: {confidence}_
• {severity_emoji} {Category} — {summary}  · _resolved by: ✅ team reaction_  (for reaction-resolved items with no GitHub issue)

*🔧 Tracked*
• {severity_emoji} {Category} — {summary}  {issue_url}  · {PR links or "No PR"}  · _worked on by: {logins}_  · _match: {confidence}_
• {severity_emoji} {Category} — {summary}  · _acknowledged by: 👍 team reaction_  (for thumbsup-acknowledged items; include issue/PR links if a match was also found)

*❌ Not tracked — no issue, no PR ({U})*

• {severity_emoji} {Category} — {summary}  · No issue · No PR
  _Question ({date}):_ {what was raised verbatim or closely paraphrased, 1–2 sentences}
  _Conclusion:_ {what the thread resolved — team agreement, next step, or "No response in thread. No issue created yet."}

*⚠️ Needs triage*
• No GitHub issue: {comma-separated list of untracked item summaries}
• No PR yet: {comma-separated list of tracked items without a PR}
```

Rules:
- One bullet per item, sorted by severity within each group: 🔴 → 🟡 → 🔵
- `severity_emoji`: 🔴 Blocking · 🟡 High · 🔵 Normal
- Issue URL as plain link (renders clickable in Slack)
- If multiple PRs: list on same line separated by `·`
- `worked on by` shows full names (resolved via `gh api /users/<login> --jq '.name'`), comma-separated; omit for ❌ Untracked items (no issue to look up)
- If `worked_on_by` is empty for a tracked/resolved item, show `_worked on by: unassigned_`
- Each Resolved and Tracked bullet ends with `· _match: {confidence}_` where confidence is `definitive`, `high`, `medium`, or `low`
- `medium` and `low` confidence matches are automatically demoted to ❌ Untracked — never shown as Resolved or Tracked
- ❌ Untracked items (including demoted ones) get two indented lines: `_Question:_` and `_Conclusion:_` drawn from full thread context
- Demoted items: Conclusion = `_(possible match: #NNN — confidence too low to confirm)_`
- No thread reply: Conclusion = `No response in thread. No issue created yet.`
- Always include the `*⚠️ Needs triage*` section at the end listing untracked items needing issues and tracked items needing PRs; omit the section only if both lists are empty
- Slack mrkdwn: `*bold*`, `_italic_`
- GitHub issue and PR links MUST use Slack pipe-link syntax — never paste raw URLs. Format: opening angle-bracket + full URL + pipe + display label + closing angle-bracket. Issue label = `Issue #NNN`. PR label = `PR #NNN`. This makes only the short label visible and clickable in Slack.
- The full structured report is posted to both webchat and Slack — not a condensed digest

**Tone rules (mandatory):**
- Neutral and factual throughout — describe what was reported, not who said it or how
- No personal opinions, names of external contacts, or company names from the feedback source
- Frame all untracked items as *areas of improvement* or *opportunities*, not complaints or problems
- Summaries describe the functional gap or enhancement, not the reporter's reaction to it
- _Question_ line: describe the underlying need or gap in one neutral sentence — not a quote or paraphrase of the original message
- _Conclusion_ line: state the recommended next step clearly and positively (e.g. "Recommended: create a GitHub issue to explore a visual rule builder")

### Step 5b — Save last-run snapshot and compute week-over-week trend

After building the report, save the current run's stats and compare against last week's snapshot.

**Snapshot directory:** `/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/snapshots/`

```python
import json, os, glob, time

SNAPSHOT_DIR = os.path.expanduser('~/.openclaw/workspace/nightly-results/customer-feedback/snapshots')
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

today = time.strftime('%Y-%m-%d')

# Snapshots are CUMULATIVE — load previous snapshot and add this run's items on top.
# This means window_from always stays at the channel start (2026-03-10).
SNAPSHOT_DIR = os.path.expanduser('~/.openclaw/workspace/nightly-results/customer-feedback/snapshots')
prev_snapshots = sorted(glob.glob(f'{SNAPSHOT_DIR}/snapshot-*.json'))
last_snapshot = json.load(open(prev_snapshots[-1])) if prev_snapshots else None

# Count THIS run's new items from FEEDBACK_ITEMS
new_by_category = {}
new_by_severity = {'🔴 Blocking': 0, '🟡 High': 0, '🔵 Normal': 0}
new_resolved = new_tracked = new_untracked = 0
for item in FEEDBACK_ITEMS:
    cat = item['category']
    new_by_category[cat] = new_by_category.get(cat, 0) + 1
    sev = item['severity']
    if sev in new_by_severity:
        new_by_severity[sev] += 1
    if item['status'].startswith('✅'):
        new_resolved += 1
    elif item['status'].startswith('🔧'):
        new_tracked += 1
    else:
        new_untracked += 1

# Merge with previous cumulative totals
prev = last_snapshot or {}
cum_by_category = dict(prev.get('by_category', {}))
for cat, count in new_by_category.items():
    cum_by_category[cat] = cum_by_category.get(cat, 0) + count

this_snapshot = {
    'date': today,
    'window_from': prev.get('window_from', '2026-03-10'),
    'window_to': today,
    'total': prev.get('total', 0) + len(FEEDBACK_ITEMS),
    'resolved': prev.get('resolved', 0) + new_resolved,
    'tracked': prev.get('tracked', 0) + new_tracked,
    'untracked': prev.get('untracked', 0) + new_untracked,
    'blocking': prev.get('blocking', 0) + new_by_severity.get('🔴 Blocking', 0),
    'high': prev.get('high', 0) + new_by_severity.get('🟡 High', 0),
    'normal': prev.get('normal', 0) + new_by_severity.get('🔵 Normal', 0),
    'by_category': cum_by_category
}

# Save this run
with open(f'{SNAPSHOT_DIR}/snapshot-{today}.json', 'w') as f:
    json.dump(this_snapshot, f, indent=2)

# Also update last-run.json for the time window tracking
last_ts_snapshot = {
    'last_ts': str(time.time()),
    'last_date': today,
    'window_from': since_date,
    'window_to': today,
    'items_found': len(FEEDBACK_ITEMS)
}
json.dump(last_ts_snapshot, open('/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/last-run.json', 'w'), indent=2)
print(f'Snapshot saved  |  Report window: {since_date} -> {today}')
```

**Compute week-over-week deltas** — compare `this_snapshot` to `last_snapshot`. For each metric, delta = this - last. Format as:
- Positive = `+N ↑` — use 🔴 for bad signals (blocking, untracked going up), ✅ for good (resolved going up)
- Negative = `-N ↓` — use ✅ for good (untracked going down), 🔴 for bad (resolved dropping)
- Zero = `no change`
- No prior snapshot = `(no prior data)`

The week-over-week table goes into **Thread reply 1 only** — not appended to the main message:

```
*[ ~ ]  Week-over-Week · <prev_date> → <today>*
```
Total items  <N>   <delta>
Resolved     <N>   <delta ✅/🔴>
Tracked      <N>   <delta>
Questions    <N>   <delta 🔴/✅>
🔴 Blocking  <N>   <delta 🔴/✅>
🟡 High      <N>   <delta>
🔵 Normal    <N>   <delta>
```
_(No prior data — trend will appear from next run)_ ← use only if no previous snapshot

*Open questions with possible GitHub issues (manual verification needed):*
For each open question (items with no GitHub issue), list one bullet with:
- severity emoji + category + summary + date
- If a possible match was found via bulk semantic matching: → _(possible match: <url|#NNN> STATE — one-line reason)_
- If nothing matched: omit the → line entirely — leave the bullet with just the severity, category, summary, and date
Use Slack pipe-link format for all issue links: <https://github.com/.../issues/NNN|#NNN>

### Step 5c — Handle file attachments (mandatory)

For every Slack message that contains a file attachment:

1. Call `https://slack.com/api/files.info?file=<FILE_ID>` with the bot token to get metadata
2. Download via the `url_private_download` field with `-H "Authorization: Bearer $SLACK_TOKEN"`
3. Extract content based on file type:
   - `.docx` — extract text with `python-docx`
   - `.pdf` — extract text with `pdfplumber` or `pypdf`
   - `.m4a`, `.mp3`, `.wav`, `.ogg`, `.webm` (audio) — transcribe with OpenAI Whisper:
     ```bash
     pip3 install --quiet --user openai-whisper
     python3 -c "import whisper; m = whisper.load_model('base'); r = m.transcribe('/tmp/audio_file'); print(r['text'])"
     ```
4. Add extracted content or transcript as `full_context` for that message. For audio items, add `_Source: voice note (transcribed)_` to the report line.

### Step 5d — Read supplement files (mandatory)

Check `/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/supplements/` for `.md` files. Treat each item as additional feedback. Move processed files to `supplements/processed/` after the report.

### Step 6 — Post to Slack #paycontrol-reports

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
post(thread_reply_1, thread_ts=ts)
post(thread_reply_2, thread_ts=ts)
```

**Main message** — new items from this run's window only (not cumulative):
```
📋 *PayControl · Customer Feedback · {since_date}–{today}*
{N} new items this week · {T} tracked · {U} untracked · {R} resolved
```
Then item sections for THIS RUN's items only, in order, all headings bold:
- *✅ Resolved* · *🔧 Tracked* · *❌ Not tracked — no issue, no PR ({U})* · *⚠️ Needs triage*
- One bullet per item with Question/Opportunity lines for untracked items
If there are no new items this window, post: `_No new feedback this week._`

**Thread reply 1** — Week-over-week table only (cumulative, all time):
Heading: *📊 Week-over-week · {prev_date} → {today}*
The comparison table and nothing else.

**Thread reply 2** — Open questions with possible GitHub matches (cumulative — all untracked items, not just this week's):
Heading: *🔍 Open questions — possible GitHub matches (manual verification needed)*
One bullet per untracked item across the full history. If a possible GitHub match exists, show it as a pipe-linked issue number with a brief note on the overlap. If nothing matched in the bulk search, omit the → line entirely — leave the bullet with severity, category, summary, and date only. Do not add any placeholder text.

To reconstruct the full historical list, read these sources **before** composing this reply:
1. `/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/slack-report-*.txt` — parse all `❌` bullets from previous reports (severity, category, summary, date)
2. `/Users/nehaeglund/.openclaw/workspace/nightly-results/customer-feedback/supplements/processed/*.md` — any supplement items that were classified as untracked
3. This run's `FEEDBACK_ITEMS` — add any new untracked items from the current window

Deduplicate by summary (exact or near-identical wording). Do not include items that were resolved or tracked in a later run (cross-check against `✅` and `🔧` bullets in the same report files). The final list is the union of all sources, minus resolved/tracked items.

**Thread reply 3** — Feedback poll about this report:
The poll questions from Step 7b, posted here instead of as a separate thread. Heading: *📊 Quick feedback on this week's report — takes 10 seconds 👆*

### Step 7 — Read last week's poll results and post new poll

#### 7a — Read last week's poll reactions

```python
import json, glob, urllib.request, os

POLL_DIR = os.path.expanduser("~/.openclaw/workspace/nightly-results/customer-feedback/polls")
poll_files = sorted(glob.glob(f"{POLL_DIR}/poll-*.json"))
last_poll = json.load(open(poll_files[-1])) if poll_files else None

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

If a previous poll exists, include results at the top of Thread reply 1 (week-over-week):

```
📊 *Last week's report feedback*
_Did the report correctly capture what customers are asking for?_
  1️⃣ {one} · 2️⃣ {two} · 3️⃣ {three}

_Were the linked GitHub issues the right ones?_
  1️⃣ {one} · 2️⃣ {two} · 3️⃣ {three}

_Did the report have good structure?_
  1️⃣ {one} · 2️⃣ {two} · 3️⃣ {three}
```
Free-text replies (q4) are not surfaced automatically — the team reads them directly in Slack.

If no previous poll exists, omit this section entirely.

#### 7b — Post this week's poll as thread replies

```python
config = json.load(open('/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json'))
token = config['bot_token']
channel = config['paycontrol_reports_channel']

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

# Thread 3 — poll (this is thread_reply_3, not a separate top-level message)
post("📊 *Quick feedback on this week's report — takes 10 seconds* 👆 React with the number that matches your answer", thread_ts=main_ts)

q1_ts = post_poll_question(
    "*1. Did the report correctly capture what customers are asking for?*\n1️⃣  Yes, accurate\n2️⃣  Some gaps\n3️⃣  Something was missed",
    thread_ts=main_ts
)
q2_ts = post_poll_question(
    "*2. Were the linked GitHub issues the right ones?*\n1️⃣  Spot on\n2️⃣  Some were wrong\n3️⃣  Mostly off",
    thread_ts=main_ts
)
q3_ts = post_poll_question(
    "*3. Did the report have good structure?*\n1️⃣  Yes, easy to follow\n2️⃣  Could be better\n3️⃣  Hard to navigate",
    thread_ts=main_ts
)

# Free-text prompt — no reactions added, just invites thread replies
post(
    "*4. Anything missing or you'd like to see differently?* Reply in this thread 👇",
    thread_ts=main_ts
)

os.makedirs(POLL_DIR, exist_ok=True)
json.dump({"date": TODAY, "q1_ts": q1_ts, "q2_ts": q2_ts, "q3_ts": q3_ts},
          open(f"{POLL_DIR}/poll-{TODAY}.json", "w"), indent=2)
```

---

## Notes

- **Never use a browser to read or interact with Slack.** Always use the Slack API directly via `curl` with the bot token. The bot is a member of `#paycontrol-feedback` and has `channels:history` scope — there is no need for a browser at any point.
- Slack token path: `/Users/nehaeglund/.openclaw/workspace/config/slack-tokens.json`
- Slack webhook path: `/Users/nehaeglund/.openclaw/workspace/config/slack-webhooks.json`
- GitHub Project: `https://github.com/orgs/PayControlLimited/projects/1`
- Feedback channel ID: `C0AKQRQ6QDA` (private, bot is member)
- **Reaction-based triage**: reactions on feedback messages drive status directly. ✅ (`white_check_mark`) = Resolved, 👍 (`+1`/`thumbsup`) = Tracked/acknowledged. Both override GitHub matching. ✅ takes priority over 👍. Requires `reactions:read` scope on the Slack bot.
- Matching is thread-context-driven: derive specific technical search phrases from the full Slack thread, then evaluate each GitHub result by reading its title and body — do not match on keyword overlap alone
- False matches are worse than no match — prefer `❌ Untracked` when unsure
- If `read:project` GraphQL scope is missing, skip Step 3 and mark all items as `❌ Untracked (project unavailable)`
- `medium` and `low` confidence matches are automatically demoted to ❌ Untracked — the report is always conservative, no human review needed
