# Falsification

Track 8 exists to attack the other tracks. Six attacks, run in
`blinkrate/track8_falsification.py`, results in
`results/track8_falsification.json`. Two of them landed.

Reproduce with `python -m blinkrate.track8_falsification`.

---

## A1 — the log-normal assumption. **Landed. Scopes the headline.**

Track 3 recovers the dispersion of a utility's daily SAIDI by inverting
`r = Phi(beta - sigma)`, then sweeps beta. That inversion assumes daily SAIDI is
log-normal. It is IEEE 1366's own assumption, but assuming it twice does not make
it true.

The harsh version of the attack holds sigma fixed and swaps the daily
distribution for a heavier-tailed one (Student-t in logs, scaled to preserve
log-scale dispersion). Retained share moves by up to 0.68 — larger than most of
the observed spread. The utility still fits a log-normal, because that is what
the standard tells it to do; only reality differs.

The harsh version is not quite fair, because track 3 never claims to know sigma.
It claims that a utility-year *reporting a given retained share* would have
reported some other value under a different beta. So the fair version re-inverts
sigma under each distribution so all of them reproduce the same observed retained
share (the sample median, 0.590), and only then compares the sweep.

| daily log distribution | matched sigma | r(1.5) | r(2.5) | r(3.0) | r(2.5)/r(1.5) |
|---|---|---|---|---|---|
| log-normal | 2.64 | 0.164 | 0.576 | 1.000 | 3.51 |
| t, nu=10 | 1.83 | 0.303 | 0.597 | 0.757 | 1.97 |
| t, nu=5 | 1.38 | 0.427 | 0.608 | 0.702 | 1.42 |
| t, nu=3 | 1.07 | 0.463 | 0.533 | 0.590 | 1.15 |

**What survives.** The direction. Under every distribution tested, a lower beta
excludes more and raises the reported improvement. That is monotone by
construction and no distributional assumption can flip it.

**What does not.** The magnitude, and it is not close. The sweep ratio spans
3.05x across these distributions. Track 3's headline range is computed under
log-normality and would be roughly half as wide under t-distributed daily logs
with 5 degrees of freedom.

**What also does not.** The cliff. Under log-normality the exclusion mechanism
switches off entirely between beta 2.90 and 2.95, because a 365-day year rarely
contains a 3-sigma day. Under heavy tails it does not switch off at all —
r(3.0) is 0.59 to 0.76 rather than 1.00, because heavy tails keep putting days
past the threshold. The cliff is a property of the log-normal, not of the rule.

**Consequence for the prose.** Every statement of track 3's magnitude and of the
cliff now carries "under IEEE 1366's own log-normal assumption" in the README and
FINDINGS. `tools/check_claims.py` fails the build if the qualifier is deleted.
Fixing this properly needs daily SAIDI series from a utility willing to publish
them, which is in ROADMAP.

---

## A2 — median versus mean in the calibration. **Survived.**

The calibration surface stores the *median* realized retained share at each
(sigma, beta), and the tracks invert that. The mean is the obvious alternative.

Across sigma from 1.0 to 6.0 the mean-minus-median gap reaches 0.131, widening
with sigma. It widens for a specific reason: at large dispersion the annual total
is essentially one day, and in the minority of draws where that day happens to
land below the threshold the realized retained share jumps to 1, which drags the
mean up while leaving the median alone.

A single filed utility-year is one realization, so the median is the right target
for a method-of-moments inversion. The gap is small enough over the range the
data actually implies (10th to 90th percentile of implied sigma is 1.35 to 4.51)
that the choice does not carry the headline. Pinned by
`test_calibration_is_median_not_mean`.

---

## A3 — the bunching estimator's specification. **Mostly survived, 32 of 36.**

Excess mass at zero exclusion, across every combination of polynomial degree
(3, 4, 5, 7), bunching window (0.02, 0.05, 0.10) and fit-range floor
(0.20, 0.30, 0.50).

- 36 specifications, excess mass from 0.88 to 62.21, median 11.91
- the 95% CI excludes 1 in 32 of them
- the four that fail are `deg7_win0.1_lo0.2`, `deg7_win0.1_lo0.3`,
  `deg7_win0.1_lo0.5` and `deg5_win0.1_lo0.5`

Every failure has the widest window (0.10) combined with a flexible polynomial.
That is the expected failure mode rather than a surprise: widen the window and
raise the degree, and the counterfactual polynomial bends up into the window and
explains the mass away. It is a real limit on the estimator and is reported as
one. The headline uses degree 5, window 0.05, floor 0.30, which sits in the
middle of the grid rather than at a favourable corner.

---

## A4 — track 2's decomposition, trimmed. **Survived.**

Track 2 attributes 82.9% of the 2013-to-2022 increase in customer-weighted
reported SAIDI to the excluded (major-event) part. Two attacks:

- drop any utility-state with even one year in the top or bottom 1% of SAIDI
  (589 to 550 utility-states): 78.7%
- drop the customer weighting entirely, so no single large utility can carry it:
  81.1%

The first version of this attack was broken and is worth recording. It kept a
utility if *any* of its four years was in range, which dropped nobody and made
the attack vacuous while appearing to pass. Caught because `n_trimmed` came back
exactly equal to `n_baseline`.

---

## A5 — track 6's ownership gap. **Landed. Two thirds of it is size.**

Pooled, investor-owned utilities have a median retained share 0.111 below
co-ops. IOUs are also roughly fifteen times larger by customer count, so the
comparison is confounded by construction.

| sample | IOU n | Coop n | IOU minus Coop median r |
|---|---|---|---|
| all | 632 | 1813 | -0.111 |
| above median size | 576 | 755 | -0.038 |
| top size decile | 293 | 1 | not comparable |

The gap shrinks by roughly two thirds once the comparison is restricted to
utilities above median size. The top-decile row is reported and flagged rather
than quoted: there is exactly one co-op in it, so the -0.370 it produces is
arithmetic, not evidence.

The regression version tells the same story. IOU status lowers the probability of
reporting zero exclusion by 18.2 points with no size control and 7.5 points with
one. Something survives, but the pooled figure overstates the ownership effect by
about 2.4x and the README now leads with the conditional number.

---

## A6 — track 1's null. **Landed. The null is underpowered.**

Track 1 finds AMI deployment associated with a coefficient of -0.185 on log
SAIDI (95% CI -0.417 to +0.048) and reports no detectable effect. A null is only
informative if the design could have seen the effect.

- minimum detectable effect at 80% power: 0.332 log points, a 28.2% SAIDI change
- the point estimate corresponds to about a 17% reduction, comfortably inside
  what the design cannot resolve
- 47.6% of 2022 utility-states are at 100% AMI and the interquartile range of AMI
  share is 0.96 to 1.00, so there is very little identifying variation left

**This is not evidence that metering deployment does not improve reliability. It
is evidence that a 2022 cross-section cannot tell.** By 2022 the treatment is
nearly universal, which is exactly the wrong time to measure it. Track 1's text
was rewritten after this attack.

---

## Attacks not run

- No attack on track 5, which is a parameter sweep rather than an estimate; its
  sensitivity to every input is the deliverable, not a robustness check.
- No placebo or permutation test on track 2's trend, because with four filing
  years and a seven-year gap there is no meaningful placebo period to permute.
- No leave-one-state-out on track 6. Would be worth adding; see ROADMAP.
