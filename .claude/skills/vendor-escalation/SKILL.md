---
name: vendor-escalation
description: Builds an evidence-based escalation to a carrier or install vendor and saves it as a draft email. Use when a vendor is late, below target, or causing aborted visits.
argument-hint: "[vendor name]"
---

Prepare an escalation to $ARGUMENTS.

1. Call `vendor_scorecard` to get this vendor's numbers and account manager contact.
2. Gather the evidence: for a carrier call `late_circuits`; for an install vendor call
   `find_sites` with install_vendor set and `at_risk_sites`.
3. Call `search_docs` for the contract terms that apply (delivery interval, credits, abort fees,
   quality target) and for the escalation runbook. Check the escalation level the runbook requires.
4. Check the vendor emails with `search_docs` for anything the vendor already told us, and
   acknowledge it in the email.
5. Write the email following the runbook: one-sentence problem with the number of sites, the
   site IDs and dates, the contract section quoted, one specific ask with a date. Factual, no blame.
6. Save it with `draft_email`, listing the related site IDs. Then tell the user where the draft is,
   which escalation level it is, and what you chose not to include and why.
