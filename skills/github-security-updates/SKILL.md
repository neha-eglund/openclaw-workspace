---
name: github-security-updates
description: Checks for outdated Maven dependencies in neha-eglund/claude-github-demo that have known security advisories in the GitHub Advisory Database, and creates deduplicated GitHub issues for SECURITY-category findings. Use when performing nightly or on-demand security update checks on the claude-github-demo repository.
---

# GitHub Security Updates

## Workflow

1. **Clone the repo**
   ```bash
   git clone https://github.com/neha-eglund/claude-github-demo /tmp/claude-github-demo
   cd /tmp/claude-github-demo
   ```

2. **Find outdated dependencies**
   ```bash
   mvn versions:display-dependency-updates -DallowSnapshots=false --no-transfer-progress | tee /tmp/versions-report.txt
   mvn versions:display-plugin-updates -DallowSnapshots=false --no-transfer-progress | tee -a /tmp/versions-report.txt
   ```
   Parse lines matching: `groupId:artifactId ... currentVersion -> latestVersion`

3. **Query GitHub Advisory Database** for each outdated dep
   ```bash
   gh api graphql -f query='{
     securityVulnerabilities(first: 5, ecosystem: MAVEN, package: "<artifactId>") {
       nodes {
         advisory { summary severity publishedAt }
         vulnerableVersionRange
         firstPatchedVersion { identifier }
       }
     }
   }'
   ```
   Use only the `artifactId` (no groupId) as the package name.

4. **Categorise** each dep:
   - **SECURITY** — current version matches a vulnerable range AND a patched version exists
   - **STALE** — major/minor lag >= 2, no advisory
   - **MINOR** — patch bump only, no advisory

5. **Create GitHub issues for SECURITY findings** (deduplicate)
   ```bash
   gh issue list --repo neha-eglund/claude-github-demo \
     --search "<artifactId> security update" --json number --jq length
   ```
   If count is 0, create:
   ```bash
   gh issue create \
     --repo neha-eglund/claude-github-demo \
     --title "[Security Update] <groupId>:<artifactId> — upgrade <currentVersion> → <latestVersion>" \
     --label "security-update,dependency-vulnerability" \
     --body "<library, versions, advisory summary, CVSS, pom.xml upgrade snippet>"
   ```

6. **Print summary** — total checked, SECURITY findings (with issue URLs), STALE deps (names only), MINOR bumps skipped
