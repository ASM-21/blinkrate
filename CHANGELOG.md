# Changelog

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
- **Rebuilt:** the capital-deployment null was an underpowered 2022
  cross-section; it is now a within-utility design over 53 metering rollouts,
  powered to detect a 24% effect.

### Reproducibility

Every committed result is regenerated in CI and must match byte for byte.
Verified identical across pandas 2.2 to 3.0, numpy 2.2 to 2.4, scipy 1.15 to
1.17 and statsmodels 0.14 to 0.15. The calibration surface is fully seeded and
rebuilt bit for bit in CI. Exact versions are in `requirements-lock.txt`.
