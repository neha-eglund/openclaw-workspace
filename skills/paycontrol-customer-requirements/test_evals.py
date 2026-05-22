"""
LLM-as-judge evals for paycontrol-customer-requirements.
Scores a dry-run report output against quality criteria.
Requires ANTHROPIC_API_KEY and a saved report file.

Run:
    python3 skills/paycontrol-customer-requirements/test_evals.py --file path/to/report.txt
"""
import argparse, os, sys
from pathlib import Path

from helpers import Runner, PASS, FAIL, SKIP

CRITERIA = [
    ("neutral_tone",      "The report is neutral and factual throughout — no personal opinions or emotional language."),
    ("positive_framing",  "Untracked items are framed as opportunities or areas of improvement, not complaints."),
    ("no_external_names", "No external company names, client names, or personal contact names appear in the report body."),
    ("bold_headings",     "All section headings use Slack bold (*heading*) format."),
    ("main_new_items",    "The main channel message contains only new items from this week's window, not cumulative history."),
    ("thread1_wow",       "Thread reply 1 contains only the week-over-week comparison table and nothing else."),
    ("thread2_questions", "Thread reply 2 contains open questions with possible GitHub issue links across the full history."),
    ("no_raw_logins",     "No raw GitHub login handles appear — only full names."),
    ("no_match_omitted",  "Items with no GitHub match do not include any 'no match found' text — the → line is absent."),
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
        prompt = f"""You are evaluating a PayControl customer feedback Slack report against a single criterion.

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
    r = Runner("Customer Feedback · Evals")
    run_evals(report_text, r)
    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
