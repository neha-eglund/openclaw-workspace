"""
LLM-as-judge evals for paycontrol-weekly-summary.
Scores a dry-run report output against quality criteria.
Requires ANTHROPIC_API_KEY and a saved report file.

Run:
    python3 skills/paycontrol-weekly-summary/test_evals.py --file path/to/report.txt
"""
import argparse, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))
from helpers import Runner, PASS, FAIL, SKIP

CRITERIA = [
    ("neutral_tone",       "The report is neutral and factual — no judgements about individuals or their work."),
    ("positive_framing",   "Stale items are framed as waiting for a decision, not as failures or neglect."),
    ("no_external_names",  "No external company names or personal contacts appear in the report."),
    ("bold_headings",      "All section headings use Slack bold (*heading*) format."),
    ("spotlights_present", "Team Spotlights appear in the main message with one bullet per contributor."),
    ("deliveries_present", "Key Deliveries appear in the main message with pipe-linked issue and PR references."),
    ("attention_section",  "The NEEDS ATTENTION section shows only 🔴 blockers in the main message."),
    ("thread1_wow",        "Thread reply 1 contains the week-over-week comparison table."),
    ("thread2_stale",      "Thread reply 2 contains stale PRs, action items, and the contributors table."),
    ("thread3_boardflow",  "Thread reply 3 contains board flow metrics including cycle time, review time, WIP, and 2 recommendations."),
    ("thread4_prtracking", "Thread reply 4 shows untracked PRs and a per-person tracked/untracked table."),
    ("no_raw_logins",      "No raw GitHub login handles appear — only full names like Apostolis Lipas."),
    ("plain_english",      "Cycle time and review time are described in plain English, not raw statistics like p50/p90."),
    ("recommendations",    "The board flow section ends with exactly 2 specific recommendations grounded in this week's data."),
]


def run_evals(report_text, r):
    try:
        import anthropic
    except ImportError:
        print(f"\n{SKIP} Skipped — run: pip3 install anthropic")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"\n{SKIP} Skipped — ANTHROPIC_API_KEY not set")
        return

    client = anthropic.Anthropic(api_key=api_key)

    for criterion_id, criterion_text in CRITERIA:
        prompt = f"""You are evaluating a PayControl weekly engineering summary Slack report against a single criterion.

Criterion: {criterion_text}

Report:
---
{report_text[:6000]}
---

Does the report satisfy this criterion?
Respond with exactly: PASS, FAIL, or PARTIAL
Then on the next line: one sentence explaining why (max 15 words).
"""
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.content[0].text.strip()
        first_line = answer.split("\n")[0].strip()
        explanation = answer.split("\n")[1].strip() if "\n" in answer else ""
        passed = first_line == "PASS"
        partial = first_line == "PARTIAL"
        icon = PASS if passed else ("⚠️ " if partial else FAIL)
        label = criterion_id.replace("_", " ")
        print(f"  {icon} {label}" + (f"\n     {explanation}" if not passed else ""))
        r.results.append((f"eval:{criterion_id}", passed, explanation))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to dry-run report file")
    args = parser.parse_args()

    report_text = Path(args.file).read_text()
    r = Runner("Weekly Summary · Evals")
    run_evals(report_text, r)
    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
