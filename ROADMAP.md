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

**EIA-861 filing years 2016-2021.** Four years with a seven-year hole is the
single biggest structural weakness. It would let track 2 date the change rather
than just measure the endpoints, and would let track 1 run with lags rather than
as a cross-section.

**Leave-one-state-out on track 6.** Named in FALSIFICATION as an attack not run.
The ownership gap already lost two thirds of its size to a size control; a few
large states could plausibly carry the rest.

**Pre-2022 AMI deployment.** Track 1's null is underpowered because AMI was
near-universal by 2022 (47.6% of utility-states at exactly 100%). The 2013-2015
Advanced Meters files, if mirrored anywhere, would put the regressor back in a
period where it still varied. That is the version of track 1 worth running.

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
