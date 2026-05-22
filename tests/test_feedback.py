"""
Static checks for the paycontrol-customer-requirements skill.

Run:
    python3 tests/test_feedback.py
"""
import sys
from helpers import Runner, SKILL_FEEDBACK, skill_contains

def main():
    r = Runner("Customer Feedback · Static checks")
    s = SKILL_FEEDBACK

    r.check("1.  Posts via chat.postMessage (not webhook)",
            skill_contains(s, r"chat\.postMessage"))

    r.check("2.  Threading — thread_ts used for replies",
            skill_contains(s, r"thread_ts"))

    r.check("3.  Channel loaded from paycontrol_reports_channel config",
            skill_contains(s, r"paycontrol_reports_channel"))

    r.check("4.  Main message = new items this week only",
            skill_contains(s, r"Main message.*new items.*this week|new items.*this week.*Main message",
                           __import__('re').IGNORECASE | __import__('re').DOTALL))

    r.check("5.  Thread 1 = week-over-week table",
            skill_contains(s, r"Thread reply 1.*[Ww]eek.over.week", __import__('re').DOTALL))

    r.check("6.  Thread 2 = cumulative open questions",
            skill_contains(s, r"Thread reply 2.*[Oo]pen questions.*cumulative|cumulative.*Thread reply 2",
                           __import__('re').IGNORECASE | __import__('re').DOTALL))

    r.check("7.  Thread 3 = feedback poll (now a separate cron job — poll removed from skill)",
            not skill_contains(s, r"Thread reply 3.*[Pp]oll", __import__('re').DOTALL))

    r.check("8.  Snapshots are cumulative from channel start",
            skill_contains(s, r"cumulative|window_from.*2026-03-10", __import__('re').IGNORECASE))

    r.check("9.  contributor-names.json loaded for worked_on_by",
            skill_contains(s, r"contributor-names\.json"))

    r.check("10. GitHub API fallback for unknown logins",
            skill_contains(s, r"gh api /users.*\.name|gh api.*users.*jq.*name"))

    r.check("11. Slack users.info for poster real name",
            skill_contains(s, r"users\.info.*real_name|real_name.*users\.info", __import__('re').DOTALL))

    r.check("12. Bulk semantic matching — 500 issues fetched",
            skill_contains(s, r"limit 500|--limit 500"))

    r.check("13. Reactions: ✅ = Resolved, 👍 = Tracked",
            skill_contains(s, r"white_check_mark.*Resolved|thumbsup.*Tracked", __import__('re').DOTALL))

    r.check("14. Voice/PDF/Word attachments handled",
            skill_contains(s, r"audio|\.m4a|\.pdf|\.docx", __import__('re').IGNORECASE))

    r.check("15. Supplement files read each run",
            skill_contains(s, r"supplements/processed"))

    r.check("16. Tone: neutral, no personal opinions",
            skill_contains(s, r"[Nn]eutral and factual|no personal opinions"))

    r.check("17. Tone: untracked items framed as opportunities",
            skill_contains(s, r"opportunit|areas of improvement", __import__('re').IGNORECASE))

    r.check("18. Tone: no external names or company names",
            skill_contains(s, r"no.*external.*names|company names|names of external", __import__('re').IGNORECASE))

    r.check("19. No-match line suppressed",
            skill_contains(s, r"omit the → line entirely|nothing matched.*omit") and
            not skill_contains(s, r"→.*_\(no match|→.*no match found"))

    r.check("20. Poll removed from skill (lives in paycontrol-reports-poll cron job)",
            not skill_contains(s, r"reactions\.add.*one.*two.*three|post_poll_question", __import__('re').DOTALL))

    r.check("21. DRY_RUN flag raises SystemExit before Slack posting",
            skill_contains(s, r"DRY_RUN") and skill_contains(s, r"raise SystemExit|SystemExit\(0\)"))

    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
