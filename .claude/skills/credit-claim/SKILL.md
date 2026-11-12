---
name: credit-claim
description: Works out the late-delivery credits a carrier owes under the contract and drafts the written claim. Use when asked about carrier credits, money owed, or late circuit penalties.
argument-hint: "[carrier name]"
---

Work out the late-delivery credits owed by $ARGUMENTS and draft the claim.

1. Call `search_docs` for "late delivery credits" and "claiming credits". Read the exact rule:
   the credit per full week late, the cap, the installation charge, and the claim deadline.
2. Call `late_circuits`. Use only this carrier's circuits that have been delivered; circuits still
   overdue are listed separately, since their final credit is not known yet.
3. Build a table: site, due date, delivered date, days late, full weeks late, credit. Apply the cap.
   Show the total and one line explaining the calculation.
4. Flag any credit whose claim deadline (60 days from delivery) is within 14 days of the program date.
5. Save a claim email to the carrier's account manager with `draft_email`. It must list site, order
   date, due date and delivery date for each circuit, as the contract requires, and quote the section.
6. Reply with the table, the total, and where the draft was saved.
