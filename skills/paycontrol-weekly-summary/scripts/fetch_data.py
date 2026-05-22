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
import json, os, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

REPOS = [
    "PayControlLimited/PayControl",
    "PayControlLimited/PayControl-PCI",
    "PayControlLimited/PayControl-GitOps",
]

now = datetime.now(timezone.utc)
since_dt = now - timedelta(days=7)
TODAY = now.strftime('%Y-%m-%d')
SINCE_DATE = since_dt.strftime('%Y-%m-%d')
SINCE = since_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
print(f"Window: {SINCE_DATE} -> {TODAY}")
json.dump({"today": TODAY, "since_date": SINCE_DATE, "since": SINCE},
          open(cfg.TMP_WINDOW, 'w'))


def gh(*args):
    result = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: gh {' '.join(args[:3])} failed: {result.stderr[:200]}", file=sys.stderr)
        return None
    return result.stdout


# --- Project board ---
print("Fetching project board...")
board_raw = gh("api", "graphql", "-f", """query={
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

board_items = []
if board_raw:
    data = json.loads(board_raw)
    nodes = data["data"]["organization"]["projectV2"]["items"]["nodes"]
    for item in nodes:
        content = item.get("content") or {}
        if not content:
            continue
        status = next(
            (fv["name"] for fv in item["fieldValues"]["nodes"]
             if fv and fv.get("field", {}).get("name") == "Status"),
            "Unknown"
        )
        board_items.append({
            "number": content.get("number"),
            "title": content.get("title", ""),
            "state": content.get("state", ""),
            "updatedAt": content.get("updatedAt", ""),
            "assignees": [a["login"] for a in content.get("assignees", {}).get("nodes", [])],
            "status": status,
        })

json.dump(board_items, open(cfg.TMP_BOARD, 'w'), indent=2)
print(f"Board: {len(board_items)} items")


# --- Per-repo data ---
for repo in REPOS:
    key = repo.replace("/", "_")
    print(f"Fetching {repo}...")

    closed_issues = gh("issue", "list", "--repo", repo, "--state", "closed",
                       "--limit", "100", "--search", f"closed:>={SINCE_DATE}",
                       "--json", "number,title,closedAt,author,labels")
    json.dump(json.loads(closed_issues or "[]"), open(f'{cfg.TMP_REPO_PREFIX}closed_issues_{key}.json', 'w'))

    open_issues = gh("issue", "list", "--repo", repo, "--state", "open",
                     "--limit", "200",
                     "--json", "number,title,createdAt,updatedAt,assignees,labels")
    json.dump(json.loads(open_issues or "[]"), open(f'{cfg.TMP_REPO_PREFIX}open_issues_{key}.json', 'w'))

    merged_prs = gh("pr", "list", "--repo", repo, "--state", "merged",
                    "--limit", "100", "--search", f"merged:>={SINCE_DATE}",
                    "--json", "number,title,createdAt,mergedAt,author,labels,additions,deletions,body")
    json.dump(json.loads(merged_prs or "[]"), open(f'{cfg.TMP_REPO_PREFIX}merged_prs_{key}.json', 'w'))

    open_prs = gh("pr", "list", "--repo", repo, "--state", "open",
                  "--limit", "100", "--json", "number,title,createdAt,author,labels,body")
    json.dump(json.loads(open_prs or "[]"), open(f'{cfg.TMP_REPO_PREFIX}open_prs_{key}.json', 'w'))

    # Direct commits (single-parent = not a merge commit)
    commits_raw = gh("api", f"/repos/{repo}/commits?sha=master&since={SINCE}&per_page=100",
                     "--jq", '[.[] | select(.parents | length == 1) | '
                             '{sha: .sha[0:7], message: (.commit.message | split("\\n")[0]), '
                             'author: .commit.author.name, email: .commit.author.email}]')
    commits = json.loads(commits_raw or "[]")
    # Filter out automated commits (bots, Flux, dependabot)
    human_commits = [c for c in commits if not any(
        x in (c.get("email", "") + c.get("author", "")).lower()
        for x in ["bot", "flux", "dependabot", "noreply", "github-actions"]
    ) and not any(
        c.get("message", "").startswith(p)
        for p in ["Update", "Merge", "Bump", "chore(deps)"]
    )]
    # Only flag as direct if not referenced by a PR (no PR number in message)
    import re
    truly_direct = [c for c in human_commits if not re.search(r'\(#\d+\)', c.get("message", ""))]
    json.dump(truly_direct, open(f'{cfg.TMP_REPO_PREFIX}direct_commits_{key}.json', 'w'))

    pc = len(json.loads(closed_issues or "[]"))
    po = len(json.loads(open_issues or "[]"))
    pm = len(json.loads(merged_prs or "[]"))
    pd = len(truly_direct)
    print(f"  closed={pc} open={po} merged={pm} direct={pd}")

print("fetch_data.py done — files written to /tmp/ws_*.json")
