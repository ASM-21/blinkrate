# blinkrate

**How much of a US utility's reported reliability number is the measurement rule
rather than the grid?**

IEEE 1366 lets utilities remove "major event days" from reported SAIDI, using a
threshold set 2.5 standard deviations up a log-normal fit to their own daily
outage history. Nobody chose 2.5 by measuring anything. This repository works out
what that choice, and the discretion around it, is worth.

**Short answer.** Re-evaluating the same filed outage records at other threshold
values moves customer-weighted fleet SAIDI from 37 min/yr to 287 min/yr — a
**7.66x range** — with no change to any underlying outage. The standard's own
value lands at 115 min/yr. Nearly a third of filings report no major event days
at all. And half the large-utility field changes quartile depending on which of
the two published series someone chose to rank on.

Built on 6,245 utility-state-years of EIA-861 reliability filings, 2013-2018 and
2022. Every headline number is regenerated from code and pinned by a test that
fails on drift.

```bash
pip install -e .
python -m blinkrate.run_all      # writes results/ and figures/
pytest                           # 56 tests
python tools/check_claims.py     # every quoted figure recomputed
python tools/utility_profile.py --name "PPL" --figure
```

---

## Seven questions

| | Question | Answer | Confidence |
|---|---|---|---|
| Q1 | What is the threshold parameter worth? | 7.66x range in fleet SAIDI; the standard sits 0.45 from where the mechanism stops working | direction solid, **magnitude assumption-dependent** |
| Q2 | Do utilities cluster where the rule rewards? | One large mass point, at *zero* exclusion — 12.0x excess mass — which is the unflattering direction | solid |
| Q3 | Does the exclusion change *who* looks reliable? | 40 to 57% of large IOUs change quartile depending on which series you rank on | solid |
| Q4 | Is the decade's deterioration weather or classification? | Both, and separable: the spikes are weather, the drift into using the rule is methodology | trend **national and solid**; the excluded-share figure is **mostly the Gulf coast** |
| Q5 | Does capital deployment show up in reliability? | No — and unlike the first version, the design could have caught a 24% effect | **bounded null** |
| Q6 | Does ownership predict exclusion? | Partly; one half of this was **retracted** when the panel doubled | weakened |
| Q7 | Is the source data internally consistent? | CAIDI identity reproduces in 100.00% of 3,838 filings | solid |

Full write-up with identification and caveats: **[FINDINGS.md](FINDINGS.md)**.
What broke under attack: **[FALSIFICATION.md](FALSIFICATION.md)**.

## The method, in one paragraph

EIA-861 publishes annual SAIDI with and without major event days, never the daily
series, so no threshold can be recomputed directly. But the exclusion has a
closed form: if daily SAIDI is log-normal — the distribution IEEE 1366 itself
assumes — the share of annual outage minutes surviving exclusion is
`r = Phi(beta - sigma)`, which depends on the dispersion of daily SAIDI and on
nothing else. Not the level, not utility size. So the two published numbers pin
the one latent parameter, and the threshold can be swept on data containing no
daily series at all. Derivation in [docs/derivation.md](docs/derivation.md).

## Why you can trust the numbers

**The closed form is not what the code uses.** It is a ratio of expectations, and
a filed utility-year is one realization of 365 days; at high dispersion those
differ by up to 0.196 in retained share. The tracks invert a simulated
median-realization surface instead, which Q7 measures at 0.018 maximum error
against the procedure IEEE 1366 actually specifies. The surface is fully seeded
and rebuilds bit-identically in about 20 seconds.

**Validation runs before the findings, not after.** Q7 checks reported CAIDI
against SAIDI/SAIFI in the source, checks the closed form against the procedural
simulator, and round-trips the inversion.

**Falsification is a track, not an appendix.** Four attacks landed. Q6's
regression result was retracted outright when the panel grew. Q1's magnitude was
scoped to its distributional assumption, and the guard fails the build if that
qualifier is deleted. Leave-one-state-out found that Q4's headline share falls
from 0.829 to 0.509 when Florida alone is removed, while every other headline
moves by under 8.4% whichever state is dropped — so Q4 was rewritten to separate
a national trend from a Gulf-coast aggregate.

**More data was allowed to break things.** The panel started at four filing
years. Finding 2016-2018 nearly doubled it, retracted one published result at
p = 0.026, turned another into a range, and let two questions be answered that
were previously marked unanswerable. Nothing was re-tuned to keep an old number.

**Claims cannot drift.** `tools/check_claims.py` pairs 59 figures quoted in the
prose with the code that recomputes them, including the numbers inside
retraction blockquotes, and also fails on missing hedges and overclaiming
language. A test feeds it a corrupted README to demonstrate that the guard can
fail.

## What is missing, stated once

- **No spending variable anywhere.** FERC Form 1 is unreachable and the Form 1
  repositories on GitHub ship extraction code, not data. Q5 regresses physical
  **deployment** instead and says so; the vegetation-management question is
  marked BLOCKED rather than proxied.
- **No weather severity index.** Q4 works around this with a geographic placebo
  built from the 2017 hurricane tracks, which is suggestive but not a direct
  test.
- **No daily SAIDI at national scale**, which is why Q1 is model-implied rather
  than measured.
- **The 2019-2021 filings**, so 2022 is a single later observation rather than a
  continuation.

Search record and mirror licences: [docs/DATA_ACCESS.md](docs/DATA_ACCESS.md).

## Layout

```
blinkrate/
  shared/ingest.py              EIA-861 harmonised across three file layouts
  shared/reliability_metrics.py MED engine, tunable beta, closed form
  shared/finite_sample.py       simulated median-realization calibration
  track1_investment.py          Q5 capital deployment, three designs
  track2_weather_split.py       Q4 weather vs classification + geographic placebo
  track3_med_sensitivity.py     Q1-Q3 threshold sweep, bunching, ranking
  track4_cause_exclusions.py    BLOCKED (FERC); loss-of-supply substituted
  track5_undergrounding.py      breakeven model, literature parameters
  track6_ownership.py           Q6 ownership stratification
  track7_validation.py          Q7 engine and source-data checks
  track8_falsification.py       six attacks on the above
  run_all.py
data/raw/                       vendored EIA-861 (US Gov, public domain)
docs/derivation.md              the exclusion identity
docs/DATA_ACCESS.md             provenance, licences, what is blocked
tools/check_claims.py           drift and overclaim guard
tools/utility_profile.py        run one utility's filed numbers through the engine
```

## Data

EIA Form 861, filing years 2013 through 2018 and 2022. US federal government
work, public domain, retrieved through GitHub mirrors because eia.gov is
unreachable from the build environment. Mirror attribution in [NOTICE](NOTICE).

MIT licensed. Citation in [CITATION.cff](CITATION.cff).
