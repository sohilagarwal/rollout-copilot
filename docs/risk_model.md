# Abort Risk Model (model card)

## Section 1 What it predicts

The chance that a site's first technician visit fails (is aborted or needs a second visit).
It scores sites that are not live yet and go live within the chosen window, usually 21 days.

## Section 2 How the score is built

Each risk factor is a chance that it alone causes a failed visit. Factors are combined as
independent chances: risk = 1 - (1 - p1) x (1 - p2) x ... Bands: High 60% or more,
Medium 30 to 59%, Low under 30%.

| Factor | Chance | Source |
|---|---|---|
| Install vendor first-visit failure rate | Learned from past visits | This program's history |
| Carrier late-delivery rate x 50% | Learned, for circuits not yet due | This program's history |
| Circuit already overdue | 90% | Assumption |
| Circuit due less than 5 days before go-live | 60% | Assumption |
| Hardware backordered past go-live | 90% | Assumption |
| Hardware backordered, due in time | 30% | Assumption |
| Hardware not shipped, go-live within 10 days | 30% | Assumption |
| Store says not ready | 90% | Assumption |
| Store readiness not confirmed, go-live within 10 days | 30% | Assumption |
| No technician booked, go-live within 7 days | 50% | Assumption |
| Previous visit aborted | 20% | Assumption |

The vendor rate leaves out failures caused by a missing circuit, because the circuit factors
already cover those.

## Section 3 How it was checked

The backtest scores every past first visit using only what was known before it: the vendor's
rate from all other visits, and whether the circuit was delivered 5 days before the visit.
It then compares the band with what happened. The `risk_forecast` tool returns the results.

## Section 4 Limits

- The data is a made-up sample, and its abort rules resemble the model's rules, so the backtest
  mostly confirms the model works as designed. On real data the backtest is the real test.
- The fixed chances are judgment calls from install experience, not measured. Replace them
  with measured rates once there are enough visits.
- Factors are treated as independent. In reality they overlap (a store remodel can delay both
  power and access), so scores with several factors are likely too high.
- The score ranks sites for attention. It is not a reason to cancel a visit without a person
  checking the site.

## Section 5 Who decides

The score only informs. Moving a go-live date is a change request that a person approves.
