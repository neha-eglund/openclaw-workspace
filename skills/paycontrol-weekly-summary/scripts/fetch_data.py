#!/usr/bin/env python3
"""
Fetch all data needed for the weekly summary:
- GitHub project board items
- Issues, PRs, and direct commits for all 3 repos

Outputs JSON files to /tmp/ws_*.json for use by the agent.

Usage:
    export GH_TOKEN=...
    python3 scripts/fetch_data.py
"""
import json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

REPOS = [
    "PayControlLimited/PayControl",
    "PayControlLimited/PayControl-PCI",
    "PayControlLimited/PayControl-GitOps",
]

BOT_SIGNALS     = ["bot", "flux", "dependabot", "noreply", "github-actions"]
COMMIT_PREFIXES = ["Update", "Merge", "Bump", "chore(deps)"]
PR_REF_PAT      = re.compile(r'\(#\d+\)')

now = datetime.now(timezone.utc)
since_dt   = now - timedelta(days=7)
TODAY      = now.strftime('%Y-%m-%d')
SINCE_DATE = since_dt.strftime('%Y-%m-%d')
SINCE      = since_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
print(f"Window: {SINCE_DATE} -> {TODAY}")
Path(cfg.TMP_WINDOW).write_text(json.dumps({"today": TODAY, "since_date": SINCE_DATE, "since": SINCE}))


def gh(*args):
    result = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: gh {' '.join(args[:3])} failed: {result.stderr[:200]}", file=sys.stderr)
        return None
    return result.stdout


def parse_board(raw):
    if not raw:
        return []
    try:
        nodes = json.loads(raw)["data"]["organization"]["projectV2"]["items"]["nodes"]
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Warning: failed to parse board response: {e}", file=sys.stderr)
        return []
    items = []
    for item in nodes:
        content = item.get("content") or {}
        if not content:
            continue
        status = next(
            (fv["name"] for fv in item["fieldValues"]["nodes"]
             if fv and fv.get("field", {}).get("name") == "Status"),
            "Unknown"
        )
        items.append({
            "number":    content.get("number"),
            "title":     content.get("title", ""),
            "state":     content.get("state", ""),
            "updatedAt": content.get("updatedAt", ""),
            "assignees": [a["login"] for a in content.get("assignees", {}).get("nodes", [])],
            "status":    status,
        })
    return items


def fetch_repo(repo):
    key = repo.replace("/", "_")

    # All 5 calls for this repo run in parallel
    def _gh_json(label, *args):
        return label, json.loads(gh(*args) or "[]")

    queries = {
        "closed_issues": (
            "issue", "list", "--repo", repo, "--state", "closed",
            "--limit", "100", "--search", f"closed:>={SINCE_DATE}",
            "--json", "number,title,closedAt,author,labels",
        ),
        "open_issues": (
            "issue", "list", "--repo", repo, "--state", "open",
            "--limit", "200",
            "--json", "number,title,createdAt,updatedAt,assignees,labels",
        ),
        "merged_prs": (
            "pr", "list", "--repo", repo, "--state", "merged",
            "--limit", "100", "--search", f"merged:>={SINCE_DATE}",
            "--json", "number,title,createdAt,mergedAt,author,labels,additions,deletions,body",
        ),
        "open_prs": (
            "pr", "list", "--repo", repo, "--state", "open",
            "--limit", "100", "--json", "number,title,createdAt,author,labels,body",
        ),
        "commits": (
            "api", f"/repos/{repo}/commits?sha=master&since={SINCE}&per_page=100",
            "--jq", '[.[] | select(.parents | length == 1) | '
                    '{sha: .sha[0:7], message: (.commit.message | split("\\n")[0]), '
                    'author: .commit.author.name, email: .commit.author.email}]',
        ),
    }

    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        results = dict(pool.map(lambda kv: (kv[0], json.loads(gh(*kv[1]) or "[]")), queries.items()))

    for label, data in results.items():
        Path(f"{cfg.TMP_REPO_PREFIX}{label}_{key}.json").write_text(json.dumps(data))

    commits = results["commits"]
    human  = [c for c in commits
              if not any(x in (c.get("email", "") + c.get("author", "")).lower() for x in BOT_SIGNALS)
              and not any(c.get("message", "").startswith(p) for p in COMMIT_PREFIXES)]
    direct = [c for c in human if not PR_REF_PAT.search(c.get("message", ""))]
    Path(f"{cfg.TMP_REPO_PREFIX}direct_commits_{key}.json").write_text(json.dumps(direct))

    print(f"  {repo.split('/')[-1]}: closed={len(results['closed_issues'])} "
          f"open={len(results['open_issues'])} merged={len(results['merged_prs'])} direct={len(direct)}")


# Fetch project board and all repos in parallel
print("Fetching board + all repos in parallel...")
with ThreadPoolExecutor(max_workers=len(REPOS) + 1) as pool:
    board_future = pool.submit(gh, "api", "graphql", "-f", """query={
  organization(login: "PayControlLimited") {
    projectV2(number: 1) {
      items(first: 100) {
        nodes {
          content {
            ... on Issue { number title state updatedAt
              assignees(first:3) { nodes { login } } }
            ... on PullRequest { number title state updatedAt }
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
}""")
    repo_futures = [pool.submit(fetch_repo, repo) for repo in REPOS]

    board_items = parse_board(board_future.result())
    for f in as_completed(repo_futures):
        f.result()  # re-raise any exception

Path(cfg.TMP_BOARD).write_text(json.dumps(board_items, indent=2))
print(f"Board: {len(board_items)} items")
print("fetch_data.py done — files written to /tmp/ws_*.json")
