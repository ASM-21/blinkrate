# Falsification

Track 8 attacks the other tracks. Six attacks, run in
`blinkrate/track8_falsification.py`, results in
`results/track8_falsification.json`. Reproduce with
`python -m blinkrate.track8_falsification`.

Four landed. Two of them landed only after the panel grew from four filing
years to seven, which is worth stating plainly: **more data retracted a
result that four years of data had supported at p = 0.026.**

---

## A1 — the log-normal assumption. **Landed. Scopes Q1's magnitude.**

Q1 recovers the dispersion of a utility's daily SAIDI by inverting
`r = Phi(beta - sigma)`, then sweeps beta. That inversion assumes daily SAIDI is
log-normal. It is IEEE 1366's own assumption, but assuming it twice does not make
it true.

The harsh version holds sigma fixed and swaps the daily distribution for a
heavier-tailed one (Student-t in logs, scaled to preserve log-scale dispersion).
Retained share moves by up to 0.68. The utility still fits a log-normal, because
that is what the standard tells it to do; only reality differs.

That version is not quite fair, because Q1 never claims to know sigma. It claims
that a utility-year *reporting a given retained share* would have reported some
other value under a different beta. So the fair version re-inverts sigma under
each distribution so all of them reproduce the same observed retained share (the
interior sample median, 0.5725), and only then compares the sweep.

| daily log distribution | matched sigma | r(1.5) | r(2.5) | r(3.0) | r(2.5)/r(1.5) |
|---|---|---|---|---|---|
| log-normal | 2.69 | 0.162 | 0.569 | 1.000 | 3.51 |
| t, nu=10 | 1.89 | 0.280 | 0.568 | 0.739 | 2.02 |
| t, nu=5 | 1.40 | 0.416 | 0.597 | 0.692 | 1.44 |
| t, nu=3 | 1.08 | 0.448 | 0.519 | 0.576 | 1.16 |

**Survives.** The direction. Under every distribution tested, a lower beta
excludes more. That is monotone by construction and no distributional assumption
can flip it.

**Does not survive.** The magnitude. The sweep ratio spans **3.03x** across
these distributions, so Q1's headline range would be roughly half as wide under
t-distributed daily logs with five degrees of freedom.

**Also does not survive: the cliff.** Under log-normality the mechanism switches
off between beta 2.90 and 2.95, because a 365-day year rarely contains a
3-sigma day. Under heavy tails it does not switch off at all — r(3.0) is 0.58 to
0.74 rather than 1.00, because heavy tails keep putting days past the threshold.
The cliff is a property of the log-normal, not of the rule.

Every statement of Q1's magnitude and of the cliff now carries the qualifier in
README and FINDINGS, and `tools/check_claims.py` fails the build if it is
deleted. Fixing this properly needs daily SAIDI from a utility willing to publish
it.

## A2 — median versus mean in the calibration. **Survived.**

The calibration surface stores the *median* realized retained share at each
(sigma, beta) and the tracks invert that. The mean is the obvious alternative.

Across sigma from 1.0 to 6.0 the mean-minus-median gap reaches 0.131, widening
with sigma, because at large dispersion the annual total is essentially one day
and in the minority of draws where that day lands below the threshold the
realized retained share jumps to 1, dragging the mean but not the median.

A filed utility-year is one realization, so the median is the right target for a
method-of-moments inversion. The gap is small over the range the data implies —
the 10th to 90th percentile of implied sigma is 1.37 to 4.72 — so the choice does
not carry any headline. Pinned by `test_calibration_is_median_not_mean`.

## A3 — the bunching estimator's specification. **Survived, 33 of 36.**

Excess mass at zero exclusion, across every combination of polynomial degree
(3, 4, 5, 7), bunching window (0.02, 0.05, 0.10) and fit-range floor
(0.20, 0.30, 0.50).

- 36 specifications, excess mass from 1.60 to 117.00, median 12.03
- the 95% CI excludes 1 in 33 of them
- the three failures are `deg7_win0.1_lo0.2`, `deg7_win0.1_lo0.3` and
  `deg7_win0.1_lo0.5`

Every failure combines the widest window with the most flexible polynomial,
which is the expected failure mode rather than a surprise: a degree-7
counterfactual fitted next to a 0.10-wide window can bend up into it and explain
the mass away. The headline uses degree 5, window 0.05, floor 0.30 — the middle
of the grid, not a favourable corner. On the seven-year panel the estimator got
more robust, not less: the minimum across specifications rose from 0.88 to 1.60.

## A4 — Q4's decomposition, trimmed. **Landed. Turns a point into a range.**

Q4 attributes 82.9% of the 2013-to-2022 rise in customer-weighted reported SAIDI
to the excluded portion. Three alternative specifications:

| specification | share from the excluded part |
|---|---|
| headline, 2013 to 2022, customer-weighted | 82.9% |
| 2013 to 2018 consecutive window | 88.0% |
| unweighted, so no single large utility carries it | 81.4% |
| top and bottom 1% of utility-years trimmed | **59.5%** |

On the four-year panel the trim moved this by four points. On the seven-year
panel it moves it by twenty-three. The reason is mechanical and worth stating
rather than explaining away: trimming extreme utility-years removes the hurricane
years, and the hurricane years are where the excluded minutes live. The trim is
not a neutral robustness check for this particular quantity. But the honest
report is a range of roughly 60% to 88%, not a point estimate, and FINDINGS now
says so.

The first version of this attack was broken and is recorded rather than quietly
fixed: it kept a utility if *any* of its years was in range, which dropped nobody
and passed vacuously. Caught because `n_trimmed` came back equal to
`n_baseline`.

## A5 — Q6's ownership gap. **Landed, and a claim was retracted.**

Pooled, investor-owned utilities have a median retained share 0.097 below
co-ops. IOUs are also roughly fifteen times larger by customer count, so the
comparison is confounded by construction.

| sample | IOU n | Coop n | IOU minus Coop median r |
|---|---|---|---|
| all | 1136 | 3317 | -0.097 |
| above median size | 1035 | 1402 | -0.027 |
| top size decile | 540 | 1 | not comparable |

The gap shrinks by roughly three quarters once the comparison is restricted to
above-median-size utilities. The top-decile row is reported and flagged rather
than quoted: there is exactly one co-op in it.

The retraction is in the regression version. On four filing years, IOU status
lowered the probability of reporting zero exclusion by 7.5 points with size
controlled, at p = 0.026, and that was published as the surviving ownership
effect. On seven years the same specification gives 3.6 points at p = 0.199.

What does survive conditioning is a different margin: IOUs exclude *more* when
they exclude (retained share 0.045 lower than co-ops, p = 0.023), even though
whether they exclude at all is explained by size. FINDINGS carries the
retraction in a blockquote, and the guard checks the retracted numbers too, so
the one paragraph most likely to go stale is not the one paragraph nothing
watches.

## A6 — Q5's null. **Survived, and this is the attack that changed the design.**

On four filing years, Q5 was a 2022 cross-section reporting no detectable effect
of AMI deployment. A6 pointed out that a null is only informative if the design
had power, and the 2022 design did not: 55% of utility-states sat at exactly
100% AMI.

That was fixed by rebuilding Q5 around the 2016-2018 filings rather than by
arguing. The attack now compares all six designs:

| design | coefficient | detectable at 80% power |
|---|---|---|
| cross-section 2016 | -0.129 | 19.7% |
| cross-section 2017 | -0.031 | 22.9% |
| cross-section 2018 | -0.038 | 28.2% |
| cross-section 2022 | -0.176 | 27.6% |
| within-utility 2016-2018 | +0.036 | 24.3% |
| long difference 2016-2018 | +0.049 | 29.6% |

Every design agrees the effect is indistinguishable from zero. The
within-utility design is the one with the identifying variation to say so, since
it is estimated off 53 utilities that actually rolled AMI out inside the window.
The null is now bounded rather than uninformative.

---

## A7 — leave one state out. **Landed on exactly one finding.**

The attack this repository most needed and had gone without. Three of its four
main headlines are customer-weighted, and Florida Power & Light files a 0.96
exclusion share on millions of customers, so any of them could have been a
Florida result wearing a national label.

Each of the 51 states and territories in the panel is dropped in turn and every
headline recomputed.

| headline | baseline | leave-one-out range | most influential | max shift |
|---|---|---|---|---|
| Q1 fleet sensitivity range | 7.66 | 7.23 to 8.30 | CA | 8.4% |
| Q2 excess mass at zero exclusion | 12.03 | 11.04 to 12.96 | NC | 8.3% |
| Q3 large IOUs changing quartile, 2022 | 52.4% | 50.0% to 53.6% | AR | 4.5% |
| Q4 share of the rise in the excluded part | 0.829 | 0.509 to 0.876 | FL | 38.6% |

**Three survive comfortably.** Q1's sensitivity range, Q2's excess mass and Q3's
ranking churn all move by under 8.4% no matter which state is removed, and the most
influential state differs for each — California, North Carolina and Arkansas
respectively — which is what you want to see. No single jurisdiction is carrying
them.

**Q4's share fails.** Removing Florida alone takes it from 0.829 to 0.509.
Removing the whole hurricane-track group takes it to 0.405.

The follow-up locates the problem precisely. Dropping the hurricane states moves
the customer-weighted share from 0.829 to 0.405 but the unweighted share only
from 0.814 to 0.743. The pattern is not absent outside the storm belt; a few very
large storm-exposed utilities are dominating a customer-weighted aggregate.
Meanwhile the everyday trend on the same panel goes from 3.08 min/yr
(p = 0.008) to 2.72 (p = 0.006) — essentially untouched.

**Q4 was rewritten rather than defended.** It now states two answers: a national
and robust one about the everyday trend, and a non-national one about the
excluded share, with the Gulf-coast dependence in the text and in the table
rather than in a footnote. `storm_state_sensitivity()` in track 2 computes the
comparison so it stays under the claims guard.

This is the third time an attack has changed a writeup, and the second time the
fix was to narrow a claim's scope rather than to drop it.

---

## Attacks not run

- Nothing attacks the undergrounding model, which is a parameter sweep rather
  than an estimate; its sensitivity to every input is the deliverable.
- No temporal placebo on Q4's trend. The geographic placebo does related work,
  but a proper temporal one needs the 2019-2021 filings.
- No leave-one-utility-out. A7 works at state granularity, and within Florida a
  single utility is most of the mass, so the utility-level version would mostly
  restate A7. Worth doing if Q4 is ever quoted at a utility level.
