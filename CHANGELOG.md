# Changelog

## v1.2.0 (2026-10)

A second literature pass, run to answer the two questions attacks A10 and A11
left open, decided one of them. The repository's central comparison is
withdrawn, and its thesis is restated on filed data only. Checking the release
on other library versions and CPUs then found that CI would have failed on its
first run, for numerical reasons rather than analytical ones; see Fixed.

### Withdrawn

- **The comparison between the threshold's effect on one utility and the
  spread between utilities** (attack A13). v1.1.0 stated it as holding only in
  one corner of two analyst choices, the tails of daily outages and the width of
  the threshold window. The literature says the working group designed 2.5 as a
  frequency target, so realistic alternatives are other frequencies, and it
  brackets them at one to fifteen major event days a year. On every such window,
  under every tail model tested including the standard's own log-normal, one
  utility's sweep is smaller than the spread between utilities. The best ratio
  anywhere is 0.86. By the falsification criterion FINDINGS commits to,
  part one of the central claim fails, and README and FINDINGS now withdraw it in
  a blockquote.

### Restated

- **The central claim, on filed data only.** Which of the two published series
  a benchmark ranks on reorders half the large-utility field, surviving
  stratification by storm exposure; how the national figure is averaged moves it
  2.07x, surviving removal of the ten largest contributors. Neither depends on a
  distributional assumption.
- **Q1's magnitude on realistic windows.** On one to fifteen major event days a
  year the threshold moves fleet SAIDI 1.52x to 3.16x depending on the tail model,
  against the 7.66x the log-normal model gives over a sweep wider than any
  alternative in the literature.
- **Q2's zero-exclusion mass point.** EIA's filing FAQ makes an identical pair
  the prescribed way to report removing nothing. Against the standard's own
  design frequency, large IEEE filers (12.2%) sit inside the range genuine
  zero-event years produce (10.3% nominal, at most 13.5%). The excess is
  concentrated in smaller utilities and self-defined-standard filers.

### Added

- **Attack A12**, Laplace tails in daily log-SAIDI, the family the working
  group's excess of major event days points to. Fails at every window.
- **Attack A13**, evidence-grounded threshold windows. The decisive attack.
- **`zero_exclusion_benchmark()`** in track 3, filed shares against the
  standard's design frequency, by reporting standard and size.
- **`tools/daily_tail_test.py`**, which tests the log-normal assumption on any
  daily outage series, including raw EAGLE-I county files. Validated on
  synthetic series of known shape before any real data exists.
- **LITERATURE.md second pass**, with the working group's own report of two to
  eight major event days a year, Fumagalli et al. (2006) as contrary evidence of
  thinner-than-normal tails, and the EIA FAQ.
- **`tools/seed_spread.py`**, which rebuilds the calibration surface from other
  seeds and reports how far each guarded figure moves.

### Corrected

- **A calibration check that turned out not to discriminate.** US event-level
  Pareto tail indices of 0.73 to 1.47 (Ahmad and Dobson 2025) first looked like
  confirmation of Laplace tails. Validating the new tail tool showed a plain
  log-normal gives a Hill index of 1.23, inside that range. The evidence is now
  described as consistent with, not establishing, heavier tails, and the tool
  reports the Hill index as not diagnostic on its own.
- **A mistaken ordering of tail weight.** The first draft of A12 described
  Laplace tails as lighter than any Student-t. That holds only beyond about 40
  standard deviations; at the standard's 2.5 Laplace implies 5.32 major event
  days a year against 3.09 for t with 15 degrees of freedom.
- **FINDINGS still said the 2.5 was "not derived from anything"**, the overclaim
  v1.0.0 corrected in the README only. It now says 2.5 was a consensus frequency
  target, not derived from any reliability outcome. FINDINGS also opened by
  counting seven questions; there are eight.
- **FINDINGS said the CAIDI identity holds "to nine significant figures."** The
  median filing agrees to about eight (relative error 6.6e-9) and the 99th
  percentile to 4.3e-8, so Q7 now says eight significant figures at the 99th
  percentile.
- **CONTRIBUTING said a calibration rebuild moves tracks 3, 6 and 8 at the third
  decimal.** A rebuild is bit-identical. A different seed is what moves numbers,
  and across five other seeds it moves 14 of the 105 guarded figures, all
  model-implied, by up to 7.7%, eight of them by more than the guard's
  tolerance. No conclusion changes. CONTRIBUTING now says so, ROADMAP lists
  quoting the seed-to-seed range as the fix, and FALSIFICATION no longer
  attributes the gap between A10's 6.04x and A8's 6.18x to resolution, since
  A8's own figure moves further than that across seeds.

### Fixed

- **The bunching estimator's last digits belonged to the LAPACK build.** Its
  counterfactual polynomial was fitted in a raw power basis with a condition
  number up to 2.3e8, so under numpy 2.5 and scipy 1.18 the stored bunching
  results no longer reproduced byte for byte and CI's first run would have
  failed. The polynomial is now fitted in a Legendre basis scaled to the fitted
  range, condition number at most 3.7 across the specification grid. It is the
  same estimator: against exact rational arithmetic its error falls from 1.6e-9
  to about 1e-14, stored results moved by at most 6.8e-9 relative, and no
  reported figure changed. Two tests pin the conditioning and the agreement.
- **Results were stored to more precision than reproduces.** At 12 significant
  figures, a regression p-value near 1e-13 changed its last stored digit under
  AMD Zen 3 code paths (numpy without AVX-512, OpenBLAS Zen kernels, selected by
  environment variable on one machine), which fails the byte check on a runner
  with that CPU whatever the library versions. Across five library stacks and
  three CPU code paths the largest disagreement on any stored value is 5.4e-12
  relative. Results are now stored to 9 significant figures, leaving every value
  at least 70 times its cross-platform spread from a rounding boundary. The
  most precise figure the prose quotes has five.
- **Verified after both fixes:** calibration bit-identical, results
  byte-identical, tests and the claims guard passing on Python 3.10 to 3.13 with
  numpy 2.2.6 to 2.5.4, pandas 2.2.3 to 3.0.6, scipy 1.15.3 to 1.18.1 and
  statsmodels 0.14.4 to 0.15.0, under both Intel AVX-512 and AMD Zen 3 code
  paths.
- **`verify.sh` failed at its first step on Python 3.12 and later**, whose venvs
  ship without setuptools while the script installed without build isolation.
  It now installs the build backend first and runs every check CI runs,
  including the calibration rebuild and the byte comparison it used to leave to
  a manual step. A test holds the two in step.
- **The README said the claims guard checks 74 figures**, the count when the
  sentence was written. It checks 105. A test now reads the count from the guard.
- **The profile tool's usage examples**, which print with `--help`, opened with
  the utility named in the README's independence disclaimer, by name and by EIA
  id, and the tool's smoke test ran on that id. The test that keeps that utility
  out of worked examples read only the prose; it now reads the code too, and the
  examples use other utilities. The README's own example, `--name "Duke
  Energy"`, matched more than one utility-state and stopped at the list of
  matches; it now names one that resolves.

## v1.1.0 (2026-09)

A second condition on the central comparison, and filed data separated from
model-implied numbers in the results themselves rather than only in the prose.

### Rescoped

- **The central comparison rests on two analyst choices, not one** (attack
  A11). v1.0.0 stated it as conditional on the tails of daily outages, with the
  threshold window held at 1.5 to 3.0. Varied symmetrically around 2.5, the
  window turns out to matter as much as the tails. Under log-normal tails the
  comparison holds only at about ±0.75 or wider, where the
  standard's own model would declare 14.7
  major event days a year at the loose end. At ±0.5 the ratio never exceeds
  0.72 under any tail tested, log-normal included. Windows are stated in
  major event days per year because that is the unit IEEE's working group judged
  2.5 on.
- **A10's breaking point is window-dependent.** Between 30 and 15 degrees of
  freedom with the 1.5 to 3.0 window; between 15 and 7 with a ±1.0 window. A10's
  table is left as run and scoped by a note in FALSIFICATION.md.

### Added

- **Schema-level provenance.** Every results file carries a `_provenance` block
  labelling each result `filed_data`, `model_implied`, `literature_model` or
  `meta`, with named exceptions where a block mixes the two. A result key that
  has not been declared refuses to save, so a new number cannot be published
  without someone deciding which kind it is. Tests hold the schema to the
  "Basis:" labels in FINDINGS and to the README's list of what holds regardless.
- `UPLOAD.md`: exact steps to publish, and what to check before and after.

### Fixed

- Stale attack counts: the README layout block still said seven attacks and the
  Zenodo metadata said ten. Both are now derived from the results by a test.
- FALSIFICATION.md opened by saying six attacks and then, two lines later, ten.
- An error message inside the claims guard still described the sample as 3,427
  utility-state-years across four filing years.

## v1.0.0 (2026-09)

First public release.

Eight questions about how measurement rules shape reported US distribution
reliability, answered on 6,245 utility-state-years of EIA-861 filings from 2013
through 2018 and 2022, with ten adversarial attacks run against the answers.

### What a reader should know before citing it

- **The critique is not new.** The instability of IEEE 1366's 2.5-beta
  threshold is established prior work (IEEE 2013; LBNL). Q1 and Q2 are
  national-scale corroboration. LITERATURE.md records what the search found and
  what it changed.
- **Two kinds of answer.** Each finding is labelled *filed data* or
  *model-implied*. Model-implied answers inherit the log-normal assumption of
  IEEE 1366 itself, and attack A10 shows the central model-implied comparison
  breaks under daily outage tails only mildly heavier than log-normal.
- **What holds regardless:** the zero-exclusion mass point, rank reversal
  between the two published series, the everyday deterioration trend and its
  geographic placebo, and the spread across aggregation rules.

### Corrections made before release

Recorded here because each changed a published sentence, and a reader of an
earlier draft should know which ones moved.

- **Retracted:** the conditional ownership effect on reporting zero exclusion
  (7.5 points at p = 0.026 on four filing years; 3.6 points at p = 0.199 on
  seven).
- **Rescoped:** "most of the rise sits in the excluded portion" is a
  customer-weighted, largely Gulf-coast result (0.829 falls to 0.509 without
  Florida); the everyday trend it sat beside is national.
- **Rescoped:** the comparison of one utility's threshold sweep against the
  spread across the industry holds under log-normal tails and fails between a
  Student-t with 30 and 15 degrees of freedom. It is now stated as conditional.
- **Corrected:** the README opened by saying nobody chose 2.5 by measuring
  anything. The IEEE working group compared alternative multipliers on donated
  utility data and judged 2.5 best against qualitative criteria. What 2.5 was
  not derived from is any reliability outcome, and the README now says that.
- **Rebuilt:** the capital-deployment null was an underpowered 2022
  cross-section; it is now a within-utility design over 53 metering rollouts,
  powered to detect a 24% effect.

### Tools

`tools/utility_profile.py` profiles any EIA-861 utility by name or id, or any
filed pair with `--pair`, and with `--tails` shows how the counterfactual sweep
shrinks under heavier-tailed daily outages while reproducing the filed value.

### Reproducibility

Every committed result is regenerated in CI and must match byte for byte.
Verified identical across pandas 2.2 to 3.0, numpy 2.2 to 2.4, scipy 1.15 to
1.17 and statsmodels 0.14 to 0.15. The calibration surface is fully seeded and
rebuilt bit for bit in CI. Exact versions are in `requirements-lock.txt`.
