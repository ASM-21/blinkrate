# Literature

Searched **after** the results existed, deliberately, so the search could not
steer the analysis. It cost this repository its framing, and this file records
what was found and specifically what changed because of it.

Short version: **the critique of IEEE 1366's 2.5-beta method is not new.** It
has been in the IEEE literature since at least 2013 and in LBNL's work since
2008. blinkrate is national-scale empirical corroboration of an established
critique, plus a method for running the sensitivity on published aggregates when
daily data is unavailable, plus two quantifications not found in the search.

---

## What was already known

**The 2.5-beta threshold is unstable, and the instability is structural.**
"Investigation of 2.5 Beta Methodology" and "Major event day segmentation"
identified fundamental problems with the method, specifically how large SAIDI
days in the right tail of the fitted log-normal distort the threshold. The
follow-up letter "2.5 Beta Methodology: Impact of 'Zero SAIDI' Days" (IEEE,
2013, DOI 10.1109/TPWRD.2013.2243918) shows that variation in the number of
zero-SAIDI days materially moves the threshold across 24 utility units, and
notes that catastrophic events cause "an unsuitable increase in the threshold
for future years."

*What this does to Q1 and Q2.* Both are corroboration, not discovery. The
self-referential property Q1 describes (a utility's exclusion allowance is set
by its own history, so a bad year buys a larger allowance later) is the same
mechanism that letter identifies. Q2's zero-exclusion mass point is the national
counterpart of a threshold effect that paper measured on 24 units.

**Alternative thresholds help some utilities and hurt others.** LBNL's
"Evaluating the Performance of the IEEE Standard 1366 Method for Identifying
Major Event Days" tested modifications to the method and found that none
"uniformly lowers the year-to-year variability in SAIDI without major events.
Instead, for any given alternative, while it may lower the value of this metric
for some utilities, it also increases it for other utilities (sometimes
dramatically)."

*What this does to Q1.* It is the closest prior work to Q1's sweep and it
reaches a compatible conclusion by a different route: they varied the method
and measured variability, this repository varies one parameter and measures the
level. Q1's contribution is the magnitude at national scale and the closed form
that makes the sweep possible without daily data.

**Major-event definitions are already known to be heterogeneous across
utilities.** LBNL's "Tracking the Reliability of the U.S. Electric Power System"
(Eto and LaCommare, OSTI 941540), covering 123 utilities across 37 state PUCs,
reports that IEEE 1366 had been formally adopted by only four state PUCs, that
fifteen required a different major-event definition, and that sixteen more had
no formal requirement at all. It also observes that the with-major-events and
without-major-events national averages are composed of *different sets of
utilities*.

*What this does to Q2 and Q3.* It substantially anticipates both. That utilities
are not using a common exclusion rule is documented; this repository quantifies
the consequence in the EIA-861 panel (29.8% reporting no exclusion, a 12.0x mass
point, a 0.18 median gap between IEEE and self-defined "Other" filers). The
observation that the two national averages rest on different utility sets is the
qualitative version of Q3's rank-reversal measurement.

**SAIDI with major event days is erratic by construction.** Standard background,
restated recently in the SALEDI resilience-metric work (arXiv:2602.07684): the
year-to-year swing in with-MED SAIDI is driven by the random occurrence of large
events rather than by underlying system condition, which is the stated rationale
for excluding them at all.

*What this does to Q4.* It supports the exclusion's purpose and is consistent
with Q4's geographic placebo. Q4's contribution is separating the weather spike
from the methodology drift empirically rather than assuming the split.

**Aggregation is a known comparability problem with a chosen answer.** APPA's
annual reliability benchmarking reports state that "to address the issues
associated with comparability, each utility's reliability statistics are
weighted based on customer count when aggregated." APPA also applies its own
major-event threshold, distinct from IEEE 1366's, in the same reports.

*What this does to Q8.* The question is recognised and a convention exists. What
the search did not turn up is a published measurement of how much the national
figure moves across aggregation rules, or of the compounding of threshold and
aggregator.

---

## What the search did not find

Stated as "not found," not as "does not exist." These are the pieces worth
attacking first if someone wants to shrink this repository's contribution
further.

1. **The closed-form inversion.** `r = Phi(beta - sigma)` as a route to sweeping
   the threshold using only the published annual with/without pair, when the
   daily series is unavailable. The prior work all has daily data.
2. **Rank reversal, quantified.** LBNL notes the two national averages rest on
   different utility sets. The measurement that 40 to 57% of large
   investor-owned utilities change performance quartile depending on which
   series is used was not found.
3. **The aggregation spread.** 2.07x across aggregation rules for one year, and
   14.32x once threshold and aggregator are swept together.
4. **The geographic placebo.** Separating weather-driven spikes from
   methodological drift using a storm-track state list applied across every year
   transition.

## What changed in this repository because of the search

- The README and FINDINGS no longer present the threshold critique as a
  discovery. Q1 and Q2 are labelled corroboration with the prior work cited
  inline.
- Q3 is scoped: the qualitative observation is LBNL's, the quantification is
  this repository's.
- Q8 is scoped the same way against the APPA convention.
- `tools/check_claims.py` now fails the build if prior-art attribution is
  deleted from the prose, or if any priority-claiming phrase appears in it. The
  banned list lives in `FORBIDDEN_NOVELTY` in that file rather than being
  quoted here, because quoting the phrases in the prose trips the check that
  forbids them. This paragraph was first written the other way and the check
  caught it.

## Sources

- "2.5 Beta Methodology: Impact of 'Zero SAIDI' Days," *IEEE Transactions on
  Power Delivery*, 2013. DOI 10.1109/TPWRD.2013.2243918
- "Investigation of 2.5 Beta Methodology" and "Major event day segmentation,"
  IEEE PES
- Eto, J. and LaCommare, K. "Tracking the Reliability of the U.S. Electric Power
  System: An Assessment of Publicly Available Information Reported to State
  Public Utility Commissions." LBNL, OSTI 941540
- "Evaluating the Performance of the IEEE Standard 1366 Method for Identifying
  Major Event Days." LBNL Energy Markets & Policy
- American Public Power Association, Annual Reliability Benchmarking Report
  (sample editions 2023-2025) and the APPA EIA-861 reliability data tool
- "Quantifying resilience for distribution system customers with SALEDI,"
  arXiv:2602.07684
- IEEE Std 1366-2012, *IEEE Guide for Electric Power Distribution Reliability
  Indices*
