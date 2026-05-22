import json, os, re, subprocess
from pathlib import Path

BASE = Path(__file__).parent.parent
SKILL_FEEDBACK = BASE / "skills/paycontrol-customer-requirements/SKILL.md"
SKILL_SUMMARY  = BASE / "skills/paycontrol-weekly-summary/SKILL.md"
TOKENS         = BASE / "config/slack-tokens.json"
NAMES          = BASE / "config/contributor-names.json"
SNAPSHOTS_CF   = BASE / "nightly-results/customer-feedback/snapshots"
SNAPSHOTS_WS   = BASE / "nightly-results/weekly-summary"

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"
SKIP = "\033[93m⏭\033[0m"


def skill_contains(skill_path, pattern, flags=0):
    return bool(re.search(pattern, skill_path.read_text(), flags))


def get_gh_token():
    try:
        d = json.loads(Path(os.path.expanduser("~/.openclaw/openclaw.json")).read_text())
        return d["env"]["vars"]["GH_TOKEN"]
    except Exception:
        return None


class Runner:
    def __init__(self, label):
        self.label = label
        self.results = []
        print(f"\n── {label} ──")

    def check(self, name, passed, detail=""):
        self.results.append((name, passed, detail))
        icon = PASS if passed else FAIL
        line = f"  {icon} {name}"
        if detail and not passed:
            line += f"\n     {detail}"
        print(line)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for _, p, _ in self.results if p)
        failed = total - passed
        print(f"\n{self.label}: {passed}/{total} passed" + (f"  ·  {failed} failed" if failed else ""))
        if failed:
            for name, p, detail in self.results:
                if not p:
                    print(f"  ❌ {name}" + (f": {detail}" if detail else ""))
        return failed == 0
