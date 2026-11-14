# Monday status: scheduled task prompt

Paste everything below the line into the prompt of a scheduled task at
claude.ai/code/routines, with this repository selected and a weekly schedule
(for example Mondays at 7:12 AM). See README, "Run it every Monday".

---

You are running the weekly status for the network rollout in this repository, unattended.
Nobody is watching, so do not wait for answers.

1. Run the weekly-status skill and save the report to reports/status-<as_of date>.md.
2. Use the risk-analyst subagent for the next 21 days. Add its table to the end of the report
   under "Risk review", including any change request IDs it filed.
3. Do not approve, reject or apply any change request, and do not call update_site or add_site.
   Change requests stay pending for the program manager to decide.
4. Do not send anything. If an escalation is needed, save it with draft_email and list the
   draft's file name in the report under "Drafts waiting for you".
5. Commit the report, any drafts in outbox/, and data/change_requests.json to a new branch named
   claude/status-<as_of date>, and push it.
6. End with three lines: overall health, number of High-risk sites, and the change requests
   waiting for approval.
