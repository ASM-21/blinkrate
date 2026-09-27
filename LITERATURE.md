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

The companion letter "Investigation of the 2.5 Beta Methodology" works from
actual daily data supplied by 12 utilities and reports that the method's
validity rests on daily SAIDI following the log-normal *in the tails*, and that
the right tail of those utilities' data does not fit it.

*What this does to A10.* It is the closest thing this repository has to direct
evidence on which side of A10's breaking point reality falls. A10 shows the
headline comparison holds only under near-log-normal tails; this letter, working
from real daily series, says the right tail departs from log-normal. That does
not pin the degree of departure, which is what A10 needs, but it points the same
way the rescope already assumes.

*What this does to Q1 and Q2.* Both are corroboration, not discovery. The
self-referential property Q1 describes (a utility's exclusion allowance is set
by its own history, so a bad year buys a larger allowance later) is the same
mechanism that letter identifies. Q2's zero-exclusion mass point is the national
counterpart of a threshold effect that paper measured on 24 units.

**Alternative thresholds help some utilities and hurt others.** LBNL's
"Evaluating the Performance of the IEEE Standard 1366 Method for Identifying
Major Event Days" tested modifications to the method and found that no
alternative reduced the year-to-year variability of SAIDI-without-major-events
across the board: each helped some utilities and made others worse, in some
cases by a lot.

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

**2.5 was a working-group judgment, not an arbitrary number.** The IEEE PES
Distribution Reliability Working Group's drafting documents describe members
donating daily outage data, comparing candidate methods and multipliers on it,
and finding none clearly superior to 2.5. A contemporaneous teaching account
gives the criteria as qualitative: not too many or too few major event days,
the right days classified, and consistency across a utility's subdivisions.

*What this does to the README.* An earlier README said nobody chose 2.5 by
measuring anything. That overstated it. The value was compared against
alternatives on real data; what it was not derived from is any reliability
outcome, and the criteria it was judged on were qualitative. The README now
says that instead.

**Aggregation is a known comparability problem with a chosen answer.** APPA's
annual reliability benchmarking reports explain that, to make utilities
comparable, each utility's statistics are weighted by customer count when
aggregated. APPA also applies its own major-event threshold, distinct from
IEEE 1366's, in the same reports.

*What this does to Q8.* The question is recognised and a convention exists. What
the search did not turn up is a published measurement of how much the national
figure moves across aggregation rules, or of the compounding of threshold and
aggregator.

---

## Second pass: the tails and the window (v1.2.0)

Run after attacks A10 and A11 left the central comparison conditional on two
questions the data could not answer: how heavy are the tails of daily outages,
and which threshold windows are realistic? Both turned out to have partial
answers in the literature, and one of them decided the comparison.

### On the tails: mixed, and weaker than it first looked

**The method's own authors saw more major event days than the model predicts.**
Warren, Bouford, Christie and colleagues, the working group paper that
introduced the method ("Classification of Major Event Days," IEEE PES General
Meeting 2003), report that on donated utility data the counts, "from two to
eight, are seen", against the 2.3 a year the log-normal model implies. They
attribute this to real data not conforming exactly to the log-normal.

*What this changed.* It is the strongest direct evidence of misfit, and it
points to heavier tails: a Laplace model of daily log-SAIDI predicts 5.32 a year at
beta 2.5, inside that range, where log-normal gives 2.27. It is not clean
evidence of tail shape, because the threshold is fitted on earlier years and
non-stationarity also produces excess exceedances. Attack A12 is built on it.

**An industry guide reports the same pattern at utility scale.** The Canadian
Electricity Association's Major Event Day Determination Reference Guide (2015)
gives one utility's whole-province count as eight days above threshold in 2014
and fifteen in 2013, and says real data "will likely not pass the p-test for
normality". *What this changed.* It supplies the loose end of the realistic
frequency window in attack A13.

**The only formal fit test found cuts the other way.** Fumagalli, Lo Schiavo,
Salvati and Secchi (IEEE Transactions on Power Systems 21(2), 2006) ran
Shapiro-Wilk tests on log daily SAIDI across 278 Italian districts. Normality
was rejected in most districts, but the distributions looked "fatter in the
middle and thinner in the tails than a standard normal". *What this changed.*
It is the main contrary evidence, and this file records it as such. It concerns
districts rather than utilities, one year at a time, under Italian rules that
exclude interruptions of three minutes or less, so it does not transfer
directly. It does mean the tail question is not settled against log-normality.

**Event-level Pareto tails, and why they discriminate less than they seem to.**
Ahmad and Dobson ("Logarithmic resilience risk metrics that address the huge
variations in blackout cost," IEEE Transactions on Power Systems 40(6), 2025)
measure tail indices of event customer cost for five US utilities between 0.73
and 1.47, all below 2. The companion SALEDI paper (arXiv:2602.07684) reports a
likelihood-ratio test finding "insufficient evidence to prefer one over the
other" between Pareto and truncated log-normal. *What this changed.* It
suggested the Laplace family for A12. Then this repository's own tail test,
validated on synthetic data, gave a plain log-normal with a log-SD of 1.8 a Hill
index of 1.23, inside the measured range. A wide log-normal mimics a Pareto tail
under the Hill estimator. So this evidence is consistent with Laplace tails and
does not establish them, and `tools/daily_tail_test.py` reports the Hill index as
not diagnostic on its own.

**Earlier IEEE work, abstract only.** Hann and Daly ("Investigation of the 2.5
Beta Methodology," IEEE Transactions on Power Systems, 2011) report, for data
from 12 utilities, problems when "the right tail of utility data sets do not fit
the log-normal distribution". Numeric results were not accessible.

**A test that should not be relied on.** A Utah Division of Public Utilities
memo in PacifiCorp's Docket 10-035-114 (2010) reports failing to reject
log-normality with a Kolmogorov-Smirnov test, but only after removing box-plot
outliers first. Removing the tail before testing the tail leaves nothing to test,
and this file cites it only as an example of that.

**Transmission blackouts, indirect.** The blackout-size literature (Carreras,
Newman and Dobson 2016; Hines and colleagues 2009) finds power-law regions in
North American transmission events, with Hines reporting only moderate support.
Different system, different events; it bears on tails only by analogy.

### On the window: 2.5 was a frequency, so alternatives are frequencies

**Christie defined major event days by how often they occur.** "Statistical
classification of major event days in distribution system reliability" (IEEE
Transactions on Power Delivery 18(4), 2003) proposes defining them "in terms of
average frequency of occurrence". The 2.5 multiplier is then just the Gaussian
quantile for a target of about 2.3 days a year, chosen by working-group
consensus, as the CEA guide also records.

*What this changed.* Everything about the window. Attack A11 had varied beta
symmetrically and left the reader to judge which window was realistic. Read as a
frequency, the literature brackets it: Italy's regulator guarantees one excluded
day a year, the working group observed two to eight, and the Canadian utility
logged fifteen. Converted through the standard's own model, the widest of these
runs from beta 1.74 to 2.78. On every such window, under
every tail model, the central comparison fails (attack A13, best ratio
0.86). This is the result that withdrew it.

No primary source was found listing which multipliers, such as 2.0 or 3.0, were
compared on donated data in 2003. The alternatives documented are methods and
frequencies: bootstrap and distribution-fitting definitions, robust estimation
for catastrophic days (explored and found not to work well in practice), two-day
rolling windows, fixed percentages of customers, and national rules abroad.

### On zero exclusion: EIA's own instructions

**An identical pair is the prescribed way to report removing nothing.** EIA's
FAQ for Form 861 tells a utility that removes no data to report the same values
under both headings; filing identical values, it says, means "you are telling us
exactly that". *What this changed.* Q2's mass point is a reporting practice
with a documented meaning, not an anomaly in the data. The open question became
how much of it is genuine years with no qualifying day, which the standard's
design frequency bounds: about 10.3% of years, at most
13.5% on the working group's observed rates. Large IEEE filers sit at
12.2%, inside that range, so Q2 was rescoped: the non-segmentation reading
holds for small and self-defined-standard filers, not for large IEEE ones.

### On data

**Daily outage data exists, just not anywhere this repository can reach.** ORNL's
EAGLE-I county outage record (Brelsford and colleagues, Scientific Data 2024,
DOI 10.1038/s41597-024-03095-5) gives customers out per county every 15 minutes
from 2014 to 2022, at 1.1 to 1.2 GB a year, distributed through Globus and
Figshare. A GitHub repository, SC-Lab-Go/SMCDC-EAGLE-I, documents the files but
does not host them. EAGLE-I approximates customer-minutes rather than measuring
SAIDI, and it omits zero rows without distinguishing them from gaps. *What this
changed.* `tools/daily_tail_test.py` accepts an EAGLE-I file directly, so the
tail question is one command away for anyone with the data.

**The 2019-2021 filings are in PUDL.** Catalyst Cooperative's PUDL publishes the
EIA-861 reliability table as `core_eia861__yearly_reliability`, distributed
through S3, Kaggle and Zenodo rather than GitHub, so still unreachable here.
PUDL issue 4907 reports a column swap in the 2024 rows only. No GitHub mirror of
the raw 2019-2021 reliability workbooks was found by searching their file names.

### Closest prior work to the rank reversal, now cited

Eto and LaCommare's assessment of utility reporting practices (IEEE PES General
Meeting 2012; LBNL-1092E, 2008) compared IEEE and non-IEEE major event
segmentation for nine utilities and found a regional average SAIDI without major
events higher than the average with them, because different utilities
contributed to each. Larsen, LaCommare, Eto and Sweeney (LBNL-188741, 2015)
regress weather on reported SAIDI. Neither measures rank reversal or separates
weather from methodology geographically, but both are the nearest neighbours of
Q3 and Q4.

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

A second, deeper pass in v1.2.0 searched IEEE PES working-group documents, LBNL,
the CEA guide, EIA's filing guidance, PUDL, and recent resilience-metric papers
for each of the four items above. None was found. The nearest neighbours are now
cited in the second-pass section: Eto and LaCommare for rank reversal, Larsen and
colleagues for weather attribution. Absence from two searches is still not
absence from the literature.

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

- "Investigation of the 2.5 Beta Methodology," IEEE letter, working from daily
  data supplied by 12 utilities
- IEEE PES Distribution Reliability Working Group, P1366 major event day
  language draft (2002) and major event white paper (2002)
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
- Warren, C. A., Bouford, J. D., Christie, R. D., et al. "Classification of
  Major Event Days." IEEE PES General Meeting, 2003, vol. 1, pp. 466-471
- Christie, R. D. "Statistical classification of major event days in
  distribution system reliability." IEEE Transactions on Power Delivery 18(4),
  2003, pp. 1336-1341
- Canadian Electricity Association. "Major Event Day Determination Reference
  Guide." 2015
- Fumagalli, E., Lo Schiavo, L., Salvati, S., Secchi, P. "Statistical
  Identification of Major Event Days: An Application to Continuity of Supply
  Regulation in Italy." IEEE Transactions on Power Systems 21(2), 2006
- Hann, M. and Daly, P. "Investigation of the 2.5 Beta Methodology." IEEE
  Transactions on Power Systems, 2011
- Ahmad and Dobson. "Logarithmic resilience risk metrics that address the huge
  variations in blackout cost." IEEE Transactions on Power Systems 40(6), 2025.
  DOI 10.1109/TPWRS.2025.3612225
- Carreras, B. A., Newman, D. E., Dobson, I. "North American blackout time
  series statistics and implications for blackout risk." IEEE Transactions on
  Power Systems 31(6), 2016. DOI 10.1109/TPWRS.2015.2510627
- Utah Division of Public Utilities. Memorandum, Docket 10-035-114, 2010
- US Energy Information Administration. FAQs for Survey Form EIA-861
- Brelsford, C., et al. "A dataset of recorded electricity outages by United
  States county 2014-2022." Scientific Data, 2024.
  DOI 10.1038/s41597-024-03095-5
- Eto, J. and LaCommare, K. "A Quantitative Assessment of Utility Reporting
  Practices for Reporting Electric Power Distribution Events." IEEE PES General
  Meeting, 2012; and LBNL-1092E, 2008
- Larsen, P., LaCommare, K., Eto, J., Sweeney, J. LBNL-188741, 2015
- Catalyst Cooperative. PUDL, table `core_eia861__yearly_reliability`
