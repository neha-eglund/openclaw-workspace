---
name: github-security-summary
description: Produces a consolidated nightly security summary for neha-eglund/claude-github-demo after the four security skills have run. Reads GitHub issues opened in the last 24 hours, collects results from pentest, PR review, dependency audit, and security updates, then prints a structured report with a ranked Action Items section. Use at the end of the nightly security suite, or standalone to get a current security status overview.
---

# GitHub Security Summary

## Workflow

1. **Collect results from GitHub** — query issues opened in the last 24h to gather what each job found:
   ```bash
   gh issue list --repo neha-eglund/claude-github-demo \
     --state open \
     --json number,title,labels,createdAt,url \
     --jq '[.[] | select(.createdAt > (now - 86400 | todate))]'
   ```

2. **Read the run history file** for 3-night trend data:
   ```
   read /Users/nehaeglund/.openclaw/workspace/nightly-results/history.md
   ```
   Extract the last 3 dated entries (most recent first) to populate the trend table.

3. **Categorise issues by label:**
   - `pentest` / `security` → Pentest findings
   - `dependency-vulnerability` + `critical` or `high` → Dependency CVEs
   - `security-update` → Security updates available
   - PR review findings come from in-session output (no issues created)

4. **Print the consolidated report** in this exact format:

```
# Nightly Security Suite — <YYYY-MM-DD>

## 1. Payment API Pentest
- Status: PASSED / FAILED / ABORTED
- Tests run: X | Passed: X | Failed: X
- New issues: <titles + URLs, or "none">
- Skipped (already tracked): <titles or "none">

## 2. PR Review
- Status: COMPLETED / NO OPEN PRS
- PRs reviewed: X | Skipped (already reviewed): X
- Blocking findings: <list per PR, or "none">
- Suggestions: <count per PR>

## 3. Dependency Audit
- Status: COMPLETED / FAILED
- Dependencies scanned: X
- CRITICAL: X | HIGH: X | MEDIUM: X | LOW: X
- New issues: <CVE IDs + URLs, or "none">
- Suppressed (MEDIUM/LOW): X

## 4. Security Updates
- Status: COMPLETED / FAILED
- Dependencies checked: X
- SECURITY findings: <dep names + issue URLs, or "none">
- STALE (no advisory): <dep names, or "none">
- MINOR bumps skipped: X

## Last 3 Nights — Consolidated Trend
<Table comparing tonight with the two prior nightly runs, drawn from history.md.
 Use "N/A" for any cell where data was unavailable (e.g. aborted run).
 Show: run date, pentest result, blocking PR issues count, CRITICAL/HIGH CVEs, stale dep issues age.>

| Date | Pentest | Blocking PR Issues | CRITICAL CVEs | HIGH CVEs | Stale Dep Issues |
|------|---------|--------------------|---------------|-----------|------------------|
| <tonight>   | X/X pass | X | X | X | X (#nn–#nn, N days) |
| <yesterday> | X/X pass | X | X | X | X (#nn–#nn, N days) |
| <2 days ago>| X/X pass | X | X | X | X (#nn–#nn, N days) |

**3-night observations:**
<2–4 bullet points noting meaningful changes or persistent issues across the 3 runs.
 Call out anything that has been unresolved for 3+ consecutive nights.
 If a finding appeared or was resolved in the window, note it.>

## Action Items
<Ranked bullet list by severity — CRITICAL first, then HIGH, then others.
 Each item: severity label, what to do, and the linked GitHub issue URL if one exists.
 Flag items that have appeared in all 3 nightly reports as "⚠️ Persisting X days".
 If nothing to act on, write: "No critical actions required today.">
```

## Notes

- If a prior skill's output is available in the session, use it directly rather than re-querying GitHub.
- Always include the date in the report header.
- Keep Action Items concrete and actionable — one line per item.
- The history.md file is append-only; always read all entries to find the last 3 distinct dates.
