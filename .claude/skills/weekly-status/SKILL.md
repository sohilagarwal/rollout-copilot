---
name: weekly-status
description: Writes the one-page Monday status report for leadership on the network rollout. Use when asked for a status report, weekly update, or leadership summary.
---

Write this week's one-page status report for leadership.

1. Call `program_summary`, `at_risk_sites` with days_ahead 21, `vendor_scorecard` and `late_circuits`.
2. Call `search_docs` for "weekly status report" and follow the format in the escalation and reporting runbook.
3. Read any leadership request in the vendor emails with `search_docs` for "leadership" and make sure the report answers it.
4. Write the report with these parts, in this order:
   - **Overall health:** On track, At risk, or Off track, and one sentence why.
   - **Numbers:** a small table: live, due in the next 3 weeks, at risk, overdue circuits, backordered hardware.
   - **Top 3 risks:** for each, sites affected (count and IDs), cause, owner, next step and date.
   - **Help needed from leadership:** specific decisions, such as approving a substitute router model.
   - **Vendor performance:** one line each, with first-time success or on-time rate against the contract target.
5. Keep it to one page. Plain words, no jargon.
6. Save it as `reports/status-<as_of date>.md` and show it in the reply.
