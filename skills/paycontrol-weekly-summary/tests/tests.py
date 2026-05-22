"""
Static checks for the paycontrol-weekly-summary skill.

Run:
    python3 skills/paycontrol-weekly-summary/tests.py
"""
import re, sys
from helpers import Runner, SKILL_SUMMARY, SCRIPTS_SUMMARY, skill_contains, skill_or_scripts_contains

def _name_resolution_before_webchat():
    text = SKILL_SUMMARY.read_text()
    resolve_pos = text.find("Resolve contributor full names")
    webchat_pos = text.find("Post to webchat")
    return resolve_pos != -1 and webchat_pos != -1 and resolve_pos < webchat_pos


def main():
    r = Runner("Weekly Summary · Static checks")
    s = SKILL_SUMMARY
    D = re.DOTALL
    IG = re.IGNORECASE

    def anywhere(pattern, flags=0):
        return skill_or_scripts_contains(s, SCRIPTS_SUMMARY, pattern, flags)

    r.check("1.  Posts via chat.postMessage (not webhook)",
            anywhere(r"chat\.postMessage"))

    r.check("2.  Threading — thread_ts used for replies",
            anywhere(r"thread_ts"))

    r.check("3.  Channel loaded from paycontrol_reports_channel config",
            anywhere(r"paycontrol_reports_channel"))

    r.check("4.  Main message includes team spotlights",
            skill_contains(s, r"TEAM SPOTLIGHTS.*Main message|Main message.*TEAM SPOTLIGHTS", IG | D))

    r.check("5.  Main message includes key deliveries",
            skill_contains(s, r"KEY DELIVERIES.*Main message|Main message.*KEY DELIVERIES", IG | D))

    r.check("6.  Main message: only 🔴 blockers under Needs Attention",
            skill_contains(s, r"NEEDS ATTENTION|only 🔴|🔴.*only", IG))

    r.check("7.  Thread 1 = week-over-week snapshot",
            skill_contains(s, r"Thread reply 1.*[Ww]eek.over.week|[Ww]eek.over.week.*Thread reply 1", D))

    r.check("8.  Thread 2 = stale items + action items + contributors",
            skill_contains(s, r"Thread reply 2.*[Ss]tale.*action|Thread reply 2.*action.*contributor", IG | D))

    r.check("9.  Thread 3 = board flow",
            skill_contains(s, r"Thread reply 3.*[Bb]oard flow|[Bb]oard flow.*Thread reply 3", D))

    r.check("10. Thread 4 = PR tracking",
            skill_contains(s, r"Thread reply 4.*[Pp][Rr] track|[Pp][Rr] track.*Thread reply 4", D))

    r.check("11. Board flow: Done this week section",
            skill_contains(s, r"Done this week", IG))

    r.check("12. Board flow: P0 in flight",
            skill_contains(s, r"P0 in flight", IG))

    r.check("13. Board flow: stale in flight (In Progress/Review, not Todo)",
            skill_contains(s, r"[Ss]tale.*[Ii]n [Pp]rogress.*[Rr]eview.*not [Tt]odo|not [Tt]odo.*[Ss]tale", D))

    r.check("14. Board flow: cycle time in plain English",
            skill_contains(s, r"plain English.*cycle time|cycle time.*plain English|Most PRs shipped", IG | D))

    r.check("15. Board flow: time to first review in plain English",
            skill_contains(s, r"first review.*plain English|plain English.*first review|first review.*24h", IG | D))

    r.check("16. Board flow: WIP per person",
            skill_contains(s, r"WIP per person|items.*in flight.*per person", IG))

    r.check("17. Board flow: throughput trend (4 weeks)",
            skill_contains(s, r"[Tt]hroughput.*4 weeks|4 weeks.*throughput|last 4 weeks", D))

    r.check("18. Board flow: exactly 2 recommendations",
            skill_contains(s, r"exactly 2 bullets|2 bullets.*[Rr]ecommendation", D))

    r.check("19. PR tracking: untracked PRs listed",
            skill_contains(s, r"❌ Untracked.*no linked issue|no linked issue.*❌", D))

    r.check("20. PR tracking: per-person table (tracked/untracked/total)",
            skill_contains(s, r"Tracked.*Untracked.*Total|per.person table.*tracked", IG | D))

    r.check("21. Name resolution runs before webchat output",
            _name_resolution_before_webchat())

    r.check("22. contributor-names.json cache loaded",
            skill_contains(s, r"contributor-names\.json"))

    r.check("23. GitHub API fallback for unknown logins",
            skill_contains(s, r"gh api /users.*\.name|gh api.*users.*jq.*name"))

    r.check("24. Posting uses threading, not background shell processes",
            anywhere(r"thread_ts") and
            not anywhere(r"post_msg\d+\.py.*&|\(sleep \d+.*python3.*\)\s*&"))

    r.check("25. Date window uses Python datetime (not date -v-7d)",
            anywhere(r"datetime.*timedelta|timedelta.*datetime") and
            not anywhere(r"date -v-7d"))

    r.check("26. Tone: neutral and positive framing",
            skill_contains(s, r"[Nn]eutral and factual|positive framing", IG))

    r.check("27. Tone: stale items not described as failures",
            skill_contains(s, r"waiting for.*decision|ready for a decision", IG))

    r.check("28. DRY_RUN flag raises SystemExit before Slack posting",
            anywhere(r"DRY_RUN") and anywhere(r"raise SystemExit|SystemExit\(0\)"))

    sys.exit(0 if r.summary() else 1)


if __name__ == "__main__":
    main()
