---
name: github-pr-review
description: Reviews all open pull requests on neha-eglund/claude-github-demo and posts structured review comments. Analyses each PR diff for correctness, security, test coverage, and code style. Skips PRs already reviewed in the last 24 hours. Use when performing nightly or on-demand PR reviews on the claude-github-demo repository.
---

# GitHub PR Review

## Workflow

1. **List open PRs**
   ```bash
   gh pr list --repo neha-eglund/claude-github-demo \
     --state open \
     --json number,title,author,headRefName,updatedAt
   ```

2. **For each PR**

   a. Skip if already reviewed in last 24h:
   ```bash
   gh pr view <number> --repo neha-eglund/claude-github-demo --json comments \
     --jq '[.comments[] | select(.createdAt > (now - 86400 | todate))] | length'
   ```
   Skip if count > 0.

   b. Fetch the diff:
   ```bash
   gh pr diff <number> --repo neha-eglund/claude-github-demo
   ```

   c. Read changed source files as needed for deeper context.

   d. Check CI status:
   ```bash
   gh pr checks <number> --repo neha-eglund/claude-github-demo
   ```

3. **Post review comment**
   ```bash
   gh pr review <number> --repo neha-eglund/claude-github-demo \
     --comment --body "<review>"
   ```
   Structure:
   ```
   **Summary**: <one-line assessment>

   **BLOCKING** (must fix before merge):
   - <security issues, correctness bugs>

   **Suggestions** (non-blocking):
   - <improvements, style>

   **Positives**:
   - <what looks good>
   ```
   If no issues, post a brief approval note.

4. **Print summary** — PRs reviewed, PRs skipped (already reviewed)
