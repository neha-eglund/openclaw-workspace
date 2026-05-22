"""
Static checks for the paycontrol-customer-feedback skill.

Run:
    python3 skills/paycontrol-customer-feedback/tests.py
"""
import re, sys
from helpers import Runner, SKILL_FEEDBACK, SCRIPTS_FEEDBACK, skill_contains, skill_or_scripts_contains

_I  = re.IGNORECASE
_IS = re.IGNORECASE | re.DOTALL
_S  = re.DOTALL

def main():
    r = Runner("Customer Feedback · Static checks")
    s = SKILL_FEEDBACK
    def anywhere(pattern, flags=0):
        return skill_or_scripts_contains(s, SCRIPTS_FEEDBACK, pattern, flags)

    r.check("1.  Posts via chat.postMessage (not webhook)",
            anywhere(r"chat\.postMessage"))

    r.check("2.  Threading — thread_ts used for replies",
            anywhere(r"thread_ts"))

    r.check("3.  Channel loaded from paycontrol_reports_channel config",
            anywhere(r"paycontrol_reports_channel"))

    r.check("4.  Main message = new items this week only",
            skill_contains(s, r"Main message.*new items.*this week|new items.*this week.*Main message",
                           _IS))

    r.check("5.  Thread 1 = week-over-week table",
            skill_contains(s, r"Thread reply 1.*[Ww]eek.over.week", _S))

    r.check("6.  Thread 2 = cumulative open questions",
            skill_contains(s, r"Thread reply 2.*[Oo]pen questions.*cumulative|cumulative.*Thread reply 2",
                           _IS))

    r.check("7.  Thread 3 = feedback poll (now a separate cron job — poll removed from skill)",
            not skill_contains(s, r"Thread reply 3.*[Pp]oll", _S))

    r.check("8.  Snapshots are cumulative from channel start",
            skill_contains(s, r"cumulative|window_from.*2026-03-10", _I))

    r.check("9.  contributor-names.json loaded for worked_on_by",
            skill_contains(s, r"contributor-names\.json"))

    r.check("10. GitHub API fallback for unknown logins",
            skill_contains(s, r"gh api /users.*\.name|gh api.*users.*jq.*name"))

    r.check("11. Slack users.info for poster real name",
            skill_contains(s, r"users\.info.*real_name|real_name.*users\.info", _S))

    r.check("12. Bulk semantic matching — 500 issues fetched",
            anywhere(r"limit.*500|500.*limit|\"500\""))

    r.check("13. Reactions: ✅ = Resolved, 👍 = Tracked",
            anywhere(r"white_check_mark|heavy_check_mark") and
            anywhere(r"Resolved|✅ Resolved") and
            anywhere(r"thumbsup|\+1") and
            anywhere(r"Tracked|🔧 Tracked"))

    r.check("14. Voice/PDF/Word attachments handled",
            skill_contains(s, r"audio|\.m4a|\.pdf|\.docx", _I))

    r.check("15. Supplement files read each run",
            skill_contains(s, r"supplements/processed"))

    r.check("16. Tone: neutral, no personal opinions",
            skill_contains(s, r"[Nn]eutral and factual|no personal opinions"))

    r.check("17. Tone: untracked items framed as opportunities",
            skill_contains(s, r"opportunit|areas of improvement", _I))

    r.check("18. Tone: no external names or company names",
            skill_contains(s, r"no.*external.*names|company names|names of external", _I))

    r.check("19. No-match line suppressed",
            anywhere(r"omit.*→.*line|only if.*match.*exists|omit line entirely", _I) and
            not anywhere(r"→.*no match found"))

    r.check("20. Poll removed from skill (lives in paycontrol-reports-poll cron job)",
            not anywhere(r"reactions\.add.*one.*two.*three|post_poll_question", _S))

    r.check("21. DRY_RUN flag raises SystemExit before Slack posting",
            anywhere(r"DRY_RUN") and anywhere(r"raise SystemExit|SystemExit\(0\)"))

    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
