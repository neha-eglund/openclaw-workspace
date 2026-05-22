#!/usr/bin/env python3
"""
Fetch GitHub project board items, PRs, and all issues for semantic matching.

Outputs:
    /tmp/cf_board.json          — project board items with status
    /tmp/cf_all_issues.json     — all issues from all 3 repos (for semantic matching)
    /tmp/cf_issue_to_prs.json   — issue number -> list of linked PRs

Usage:
    export GH_TOKEN=...
    python3 scripts/fetch_github.py
"""
import json, re, subprocess, sys

REPOS = [
    ("PayControlLimited/PayControl",        "PayControl"),
    ("PayControlLimited/PayControl-PCI",    "PayControl-PCI"),
    ("PayControlLimited/PayControl-GitOps", "PayControl-GitOps"),
]


def gh(*args):
    result = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: {' '.join(args[:3])} failed: {result.stderr[:200]}", file=sys.stderr)
        return None
    return result.stdout


# --- Project board ---
print("Fetching project board...")
board_raw = gh("api", "graphql", "-f", """query={
  organization(login: "PayControlLimited") {
    projectV2(number: 1) {
      items(first: 200) {
        nodes {
          content {
            ... on Issue { number title state url body }
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

board = []
if board_raw:
    nodes = json.loads(board_raw)["data"]["organization"]["projectV2"]["items"]["nodes"]
    for item in nodes:
        content = item.get("content") or {}
        if not content:
            continue
        status = next(
            (fv["name"] for fv in item["fieldValues"]["nodes"]
             if fv and fv.get("field", {}).get("name") == "Status"),
            "Unknown"
        )
        board.append({
            "number": content.get("number"),
            "title":  content.get("title", ""),
            "state":  content.get("state", ""),
            "url":    content.get("url", ""),
            "body":   (content.get("body") or "")[:400],
            "status": status,
        })

json.dump(board, open('/tmp/cf_board.json', 'w'), indent=2)
print(f"Board: {len(board)} items")


# --- All issues (for semantic matching) + PR index ---
all_issues = []
all_prs = []

for repo, repo_name in REPOS:
    print(f"Fetching issues from {repo}...")
    raw = gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "500",
             "--json", "number,title,state,url,body,labels,assignees")
    issues = json.loads(raw or "[]")
    for i in issues:
        i["body"] = (i.get("body") or "")[:400]
        i["repo"] = repo_name
    all_issues.extend(issues)

    print(f"Fetching PRs from {repo}...")
    raw = gh("pr", "list", "--repo", repo, "--state", "all", "--limit", "200",
             "--json", "number,title,body,state,url,closingIssuesReferences")
    prs = json.loads(raw or "[]")
    for pr in prs:
        pr["repo"] = repo_name
        pr["body"] = (pr.get("body") or "")[:300]
    all_prs.extend(prs)

json.dump(all_issues, open('/tmp/cf_all_issues.json', 'w'), indent=2)
print(f"Total issues: {len(all_issues)}")

# Build issue -> PR index
close_pat = re.compile(r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)', re.IGNORECASE)
bare_pat  = re.compile(r'(?<!\d)#(\d+)(?!\d)')

issue_to_prs = {}
for pr in all_prs:
    refs = set(str(i["number"]) for i in pr.get("closingIssuesReferences", []))
    text = f"{pr['title']} {pr.get('body', '')}"
    refs.update(m.group(1) for m in close_pat.finditer(text))
    refs.update(bare_pat.findall(pr["title"]))
    for inum in refs:
        entry = {"number": pr["number"], "state": pr["state"],
                 "repo": pr["repo"], "url": pr["url"]}
        existing = issue_to_prs.setdefault(inum, [])
        if not any(e["number"] == entry["number"] and e["repo"] == entry["repo"]
                   for e in existing):
            existing.append(entry)

json.dump(issue_to_prs, open('/tmp/cf_issue_to_prs.json', 'w'), indent=2)
print(f"PR index: {len(issue_to_prs)} issues with linked PRs")
print("fetch_github.py done.")
