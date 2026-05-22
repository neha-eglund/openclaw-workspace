"""
LLM-as-judge evals — scores a dry-run report output against quality criteria.
Requires ANTHROPIC_API_KEY and a saved report file.

Run:
    python3 tests/test_evals.py --file tests/logs/2026-05-21-11-58.log --skill summary
    python3 tests/test_evals.py --file tests/logs/2026-05-21-11-58.log --skill feedback
"""
import argparse, os, sys
from pathlib import Path
from helpers import Runner, PASS, FAIL, SKIP

CRITERIA_FEEDBACK = [
    ("neutral_tone",      "The report is neutral and factual throughout — no personal opinions or emotional language."),
    ("positive_framing",  "Untracked items are framed as opportunities or areas of improvement, not complaints."),
    ("no_external_names", "No external company names, client names, or personal contact names appear in the report body."),
    ("bold_headings",     "All section headings use Slack bold (*heading*) format."),
    ("main_new_items",    "The main channel message contains only new items from this week's window, not cumulative history."),
    ("thread1_wow",       "Thread reply 1 contains only the week-over-week comparison table and nothing else."),
    ("thread2_questions", "Thread reply 2 contains open questions with possible GitHub issue links across the full history."),
    ("thread3_poll",      "Thread reply 3 contains the feedback poll with 4 questions, Q4 being free text."),
    ("no_raw_logins",     "No raw GitHub login handles appear — only full names."),
    ("no_match_omitted",  "Items with no GitHub match do not include any 'no match found' text — the → line is absent."),
    ("poll_structure_q",  "The poll's third question asks about report structure, not tone."),
]

CRITERIA_SUMMARY = [
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
    ("poll_structure_q",   "The poll's third question asks about report structure, not tone."),
]


def run_evals(report_text, skill, r):
    try:
        import anthropic
    except ImportError:
        print(f"\n{SKIP} Skipped — run: pip3 install anthropic")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"\n{SKIP} Skipped — ANTHROPIC_API_KEY not set")
        return

    criteria = CRITERIA_FEEDBACK if skill == "feedback" else CRITERIA_SUMMARY
    client = anthropic.Anthropic(api_key=api_key)

    for criterion_id, criterion_text in criteria:
        prompt = f"""You are evaluating a PayControl Slack report against a single criterion.

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
    parser.add_argument("--skill", choices=["feedback", "summary"], required=True)
    args = parser.parse_args()

    report_text = Path(args.file).read_text()
    skill_label = "Customer Feedback" if args.skill == "feedback" else "Weekly Summary"
    r = Runner(f"{skill_label} · Evals")
    run_evals(report_text, args.skill, r)
    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
