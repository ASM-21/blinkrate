# Roadmap

Ordered by how much each item would change a conclusion, not by effort.

## Would settle an open falsification result

**Daily SAIDI series from any utility.** Track 3's sensitivity is model-implied
because no daily outage series is public at national scale. Attack A1 showed the
magnitude of the result does not survive dropping log-normality even though its
direction does. A single utility's five-year daily SAIDI series would replace the
inversion with a measurement and close A1 outright. Some state commissions
require daily outage logs in annual reliability filings; those are per-state PDF
or spreadsheet attachments, not a dataset, so this is a scraping and parsing job
rather than a download.

**A storm severity index keyed to service territories.** Track 2 cannot separate
weather severity from classification, which is the question it exists to answer.
NOAA Storm Events with county-level footprints, crossed with utility service
territory shapefiles from HIFLD, would do it. Both are blocked here.

**FERC Form 1.** Restores the spending variable to track 1 and unblocks track 4
entirely. PUDL distributes processed Form 1 via Zenodo.

## Would strengthen what is already here

**EIA-861 filing years 2019-2021.** Partly done: 2016-2018 were found in
`IMMM-SFA/electricity_entity_boundaries` and folded in, which closed most of the
gap and changed three conclusions. What remains is 2019-2021, without which 2022
is a single later observation rather than a continuation and no movement after
2018 can be dated.

**Leave-one-utility-out.** Leave-one-state-out is now attack A7 and it found
that Q4's excluded-share headline is largely Florida. Within Florida a single
utility is most of the mass, so the utility-level version would mostly restate
A7 — but it becomes necessary the moment Q4 is quoted at a utility level.

**A weighted aggregate keyed to something other than customer count.** Done in
part: track 9 reports six aggregation rules and shows they span 2.07x for a
single year, with threshold and aggregator together spanning 14.32x. What is
still missing is a weight that is not derived from the filings themselves —
state population, or customer-hours at risk — which would let the national
figure be checked against something exogenous rather than only reweighted.

**Leave-one-utility-out inside Florida.** A7 works at state granularity. Within
Florida a single co-operative reported over nine days per customer after
Hurricane Ian, so the utility-level jackknife is the natural next cut and
becomes necessary the moment Q4 or Q8 is quoted at utility level.

**Pre-2016 AMI deployment.** Done for 2016-2018, which was enough to rebuild Q5
around a within-utility design and turn an underpowered null into a bounded one.
The 2013-2015 Advanced Meters files would extend the rollout window further back,
to where AMI share varied most.

**A bunching estimator with a proper counterfactual.** The current excess-mass
estimator extrapolates a polynomial, and A3 showed four of 36 specifications kill
it. A structural counterfactual, drawing the retained-share density implied by
the fitted sigma distribution, would be less arbitrary.

## Deliberately not planned

**Utility-level causal claims about investment.** Nothing in the reachable data
supports them, and adding controls to a 2022 cross-section will not create
identification.

**Extending to non-US grids.** The whole repo is about one standard's threshold
parameter and one national filing form. Other jurisdictions use different
exclusion rules, which makes it a different project rather than a bigger sample.
