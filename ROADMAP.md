# Roadmap

Ordered by how much each item would change a conclusion, not by effort.

## Would settle an open falsification result

**Daily SAIDI for more utilities, and the reported series.** Partly done.
Attack A14 tests the log-normal assumption on PG&E's and FPL's outage maps,
archived by git scraping, and it fails for both; on them the log-normal model
also overstates the threshold's measured effect in two of three utility-years.
What is missing is breadth and the reported series: two large utilities in
extreme-weather states, measured as outage-map estimates. Three routes, cheapest
first. Other git-scraping archives of outage maps may exist for other
utilities, and `tools/build_outage_snapshots.py` takes a new one in a few lines.
EAGLE-I's county record covers the country at 15-minute resolution;
`tools/daily_tail_test.py` reads it directly, but it is too large to vendor and
unreachable from the build environment. And daily SAIDI as utilities record it
for the standard itself, which surfaces in some state reliability proceedings,
would test the reported series rather than an estimate of it. None of this would revive the withdrawn
comparison: A13 found it fails on every evidence-grounded window even under
log-normal tails.

**A storm severity index keyed to service territories.** Track 2 cannot separate
weather severity from classification, which is the question it exists to answer.
NOAA Storm Events with county-level footprints, crossed with utility service
territory shapefiles from HIFLD, would do it. Both are blocked here.

**FERC Form 1.** Restores the spending variable to track 1 and unblocks track 4
entirely. PUDL distributes processed Form 1 via Zenodo.

## Would strengthen what is already here

**Monte Carlo error on model-implied figures.** The calibration surface is a
seeded simulation, so model-implied figures reproduce bit for bit without being
exact. Across five other seeds, 19 of the 118 guarded figures change, by up to
7.7%: the 7.66x threshold range spans 7.69x to 7.75x and the 14.32x combined
space 14.22x to 14.82x. No conclusion changes, but several figures are quoted
more finely than their Monte Carlo error allows, and the leave-one-state-out
bound "under 8.4%" reaches 8.43% under one seed. Quoting the seed-to-seed range
beside each model-implied figure, or raising the simulation count until that
range sits inside the quoted precision, would fix it. `tools/seed_spread.py`
measures it.

**EIA-861 filing years 2019-2021.** Partly done: 2016-2018 were found in
`IMMM-SFA/electricity_entity_boundaries` and folded in, which closed most of the
gap and changed three conclusions. What remains is 2019-2021, without which 2022
is a single later observation rather than a continuation and no movement after
2018 can be dated.

**Leave-one-utility-out.** Done as attack A9: dropping the ten largest
contributors to national customer-outage-minutes moves Q8's aggregation spread
from 2.07x to 2.00x.

**A weighted aggregate keyed to something other than customer count.** Done in
part: track 9 reports six aggregation rules and shows they span 2.07x for a
single year, with threshold and aggregator together spanning 14.32x. What is
still missing is a weight that is not derived from the filings themselves
(state population, or customer-hours at risk), which would let the national
figure be checked against something exogenous rather than only reweighted.

**A frequency-based major event definition, run end to end.** Christie's 2003
framing defines major event days by how often they occur. Re-expressing every
model-implied result in the repository in major event days per year, rather than
in beta, would make them directly comparable with the frequencies regulators and
the working group actually discuss.

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
