import json, os, re
from pathlib import Path

BASE = Path(__file__).parent.parent.parent

SKILL_SUMMARY   = Path(__file__).parent.parent / "SKILL.md"
SCRIPTS_SUMMARY = Path(__file__).parent.parent / "scripts"

TOKENS       = BASE / "config/slack-tokens.json"
NAMES        = BASE / "config/contributor-names.json"
SNAPSHOTS_WS = BASE / "nightly-results/weekly-summary"

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"
SKIP = "\033[93m⏭\033[0m"


def skill_contains(skill_path, pattern, flags=0):
    return bool(re.search(pattern, skill_path.read_text(), flags))


def skill_or_scripts_contains(skill_path, scripts_dir, pattern, flags=0):
    texts = [skill_path.read_text()]
    if scripts_dir.exists():
        texts += [f.read_text() for f in scripts_dir.glob("*.py")]
    return any(bool(re.search(pattern, t, flags)) for t in texts)


def get_gh_token():
    if tok := os.environ.get("GH_TOKEN"):
        return tok
    try:
        d = json.loads(Path(os.path.expanduser("~/.openclaw/openclaw.json")).read_text())
        return d["env"]["vars"]["GH_TOKEN"]
    except Exception:
        return None


def get_slack_token(key="reports_bot_token"):
    if key == "reports_bot_token" and (tok := os.environ.get("SLACK_TOKEN")):
        return tok
    if TOKENS.exists():
        return json.loads(TOKENS.read_text()).get(key, "")
    return ""


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
