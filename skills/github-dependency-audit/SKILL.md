---
name: github-dependency-audit
description: Runs an OWASP Dependency-Check audit against neha-eglund/claude-github-demo and creates deduplicated GitHub issues for HIGH and CRITICAL CVEs found in Maven dependencies. Use when performing nightly or on-demand dependency vulnerability scanning on the claude-github-demo repository.
---

# GitHub Dependency Audit

## Workflow

1. **Clone the repo**
   ```bash
   git clone https://github.com/neha-eglund/claude-github-demo /tmp/claude-github-demo
   cd /tmp/claude-github-demo
   ```

2. **Run OWASP Dependency-Check**
   ```bash
   mvn org.owasp:dependency-check-maven:check \
     -DfailBuildOnCVSS=11 \
     -Dformat=JSON \
     -DprettyPrint=true \
     -DskipTestScope=false \
     --no-transfer-progress
   ```
   `-DfailBuildOnCVSS=11` prevents build failure (CVSS max is 10) — escalation is handled manually.
   If `NVD_API_KEY` is set, add `-DnvdApiKey=$NVD_API_KEY` to avoid rate limiting.

3. **Parse report** at `target/dependency-check-report.json`
   ```
   .dependencies[].vulnerabilities[]
   Fields: .name (CVE ID), .severity, .cvssv3.baseScore, .description
   ```
   Filter: CRITICAL (score >= 9.0) and HIGH (score >= 7.0).

4. **Create GitHub issues** (deduplicate)
   ```bash
   gh issue list --repo neha-eglund/claude-github-demo \
     --search "<CVE-ID>" --json number --jq length
   ```
   If count is 0, create:
   ```bash
   gh issue create \
     --repo neha-eglund/claude-github-demo \
     --title "[Dependency] <CVE-ID> — <affected library> (<severity>)" \
     --label "dependency-vulnerability,<critical or high>" \
     --body "<CVE ID, dep+version, CVSS score, description, remediation>"
   ```

5. **Print summary** — total deps scanned, count by severity (CRITICAL/HIGH/MEDIUM/LOW), CVEs escalated (with URLs), CVEs suppressed
