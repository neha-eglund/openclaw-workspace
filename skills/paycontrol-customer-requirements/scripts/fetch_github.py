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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

REPOS = cfg.REPOS

BODY_LIMIT_ISSUE = 400
BODY_LIMIT_PR    = 300

close_pat = re.compile(r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)', re.IGNORECASE)
bare_pat  = re.compile(r'(?<!\d)#(\d+)(?!\d)')


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
            "number": content.get("number"),
            "title":  content.get("title", ""),
            "state":  content.get("state", ""),
            "url":    content.get("url", ""),
            "body":   (content.get("body") or "")[:BODY_LIMIT_ISSUE],
            "status": status,
        })
    return items


def fetch_repo(repo, repo_name):
    # Issues and PRs fetched in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        issues_f = pool.submit(gh, "issue", "list", "--repo", repo, "--state", "all",
                               "--limit", "500",
                               "--json", "number,title,state,url,body,labels,assignees")
        prs_f    = pool.submit(gh, "pr", "list", "--repo", repo, "--state", "all",
                               "--limit", "200",
                               "--json", "number,title,body,state,url,closingIssuesReferences")
        issues = json.loads(issues_f.result() or "[]")
        prs    = json.loads(prs_f.result() or "[]")

    for i in issues:
        i["body"] = (i.get("body") or "")[:BODY_LIMIT_ISSUE]
        i["repo"] = repo_name
    for pr in prs:
        pr["repo"] = repo_name
        pr["body"] = (pr.get("body") or "")[:BODY_LIMIT_PR]

    print(f"  {repo_name}: {len(issues)} issues, {len(prs)} PRs")
    return issues, prs


# Fetch board and all repos in parallel
print("Fetching board + all repos in parallel...")
all_issues = []
all_prs    = []

with ThreadPoolExecutor(max_workers=len(REPOS) + 1) as pool:
    board_future = pool.submit(gh, "api", "graphql", "-f", """query={
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
    repo_futures = {pool.submit(fetch_repo, repo, name): name for repo, name in REPOS}

    board = parse_board(board_future.result())
    for future in as_completed(repo_futures):
        issues, prs = future.result()
        all_issues.extend(issues)
        all_prs.extend(prs)

Path(cfg.TMP_BOARD).write_text(json.dumps(board, indent=2))
print(f"Board: {len(board)} items")

Path(cfg.TMP_ALL_ISSUES).write_text(json.dumps(all_issues, indent=2))
print(f"Total issues: {len(all_issues)}")

# Build issue -> PR index using a set for O(1) deduplication
issue_to_prs = {}
seen = {}

for pr in all_prs:
    refs = set(str(i["number"]) for i in pr.get("closingIssuesReferences", []))
    text = f"{pr['title']} {pr.get('body', '')}"
    refs.update(m.group(1) for m in close_pat.finditer(text))
    refs.update(bare_pat.findall(pr["title"]))
    for inum in refs:
        key = (pr["number"], pr["repo"])
        bucket = seen.setdefault(inum, set())
        if key not in bucket:
            bucket.add(key)
            issue_to_prs.setdefault(inum, []).append({
                "number": pr["number"],
                "state":  pr["state"],
                "repo":   pr["repo"],
                "url":    pr["url"],
            })

Path(cfg.TMP_ISSUE_PRS).write_text(json.dumps(issue_to_prs, indent=2))
print(f"PR index: {len(issue_to_prs)} issues with linked PRs")
print("fetch_github.py done.")
