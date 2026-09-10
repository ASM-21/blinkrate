# blinkrate

**How much of a US utility's reported reliability number is the measurement rule
rather than the grid?**

IEEE 1366 lets utilities remove "major event days" from reported SAIDI, using a
threshold set 2.5 standard deviations up a log-normal fit to their own daily
outage history. Nobody chose 2.5 by measuring anything. This repo works out what
that choice is worth.

Answer: at the fleet level, moving the threshold parameter from 1.5 to 3.0 moves
customer-weighted reported SAIDI from 39 min/yr to 259 min/yr — **6.62x**, with
no change to any underlying outage. The standard's own value lands at
**114 min/yr**. Meanwhile **30.3% of filings** report no major event days at
all, which the standard's own model says should be rare.

Built on 3,427 utility-state-years of EIA-861 reliability filings. Every headline
number is regenerated from code and pinned by a test that fails on drift.

```bash
pip install -e .
python -m blinkrate.run_all      # writes results/ and figures/
pytest                           # 49 tests
python tools/check_claims.py     # every quoted figure recomputed
python tools/utility_profile.py --name "PPL" --figure
```

---

## Findings

| # | Question | Answer | Confidence |
|---|---|---|---|
| 3 | What is the threshold parameter worth? | 6.62x range in fleet SAIDI; the standard sits 0.45 from where the mechanism stops working | direction solid, **magnitude assumption-dependent** |
| 3 | Do utilities cluster at zero exclusion? | Yes — **9.3x** excess mass, 32 of 36 specifications | solid |
| 2 | Is the decade's deterioration weather or performance? | **82.9% of the** increase is in the excluded part | solid, but **cannot separate weather severity from classification** |
| 3 | Does the exclusion change *who* looks reliable? | **52%** of large IOUs change quartile depending on which series you rank on | solid |
| 6 | Does ownership predict exclusion? | IOU median retained share **0.644** vs municipal **0.926**, but two thirds of the gap is size | weakened by falsification |
| 4 | Do cause carve-outs stack? | Loss-of-supply removes another 4% (retained **0.960**); both together leave 59.3% | solid, descriptive |
| 1 | Does capital deployment predict reliability? | AMI coefficient **-0.185**, CI crosses zero — and the design could not have detected it | **underpowered null** |
| 5 | Does undergrounding pay back? | Needs **1,633 min/yr** baseline SAIDI at **30.5 customers per** mile; median utility reports 174 | model, not measurement |
| 7 | Is the source data internally consistent? | CAIDI identity reproduces in **100%** of 887 filings | solid |

Full write-up with caveats attached: [FINDINGS.md](FINDINGS.md).
What broke under attack: [FALSIFICATION.md](FALSIFICATION.md).

## Why you can trust the numbers

**The method is one identity, written out.** If daily SAIDI is log-normal — the
distribution IEEE 1366 itself assumes — the share of annual outage minutes that
survives exclusion is `r = Phi(beta - sigma)`. It depends on the dispersion of
daily SAIDI and on nothing else: not the level, not utility size. That means the
two numbers EIA-861 publishes pin the one latent parameter, and the threshold can
be swept on data that contains no daily series at all. Derivation in
[docs/derivation.md](docs/derivation.md).

**The closed form is not what the code uses.** It is a ratio of expectations, and
a filed utility-year is one realization of 365 days. At high dispersion those
differ by up to 0.196 in retained share. The tracks invert a simulated
median-realization surface instead, which track 7 measures at 0.018 maximum
error against the procedure IEEE 1366 actually specifies.

**Validation runs before the findings, not after.** Track 7 checks the reported
CAIDI against SAIDI/SAIFI in the source (100% of 887 filings reproduce to nine
significant figures), checks the closed form against the procedural simulator,
and round-trips the inversion (max error 0.017).

**Falsification is a track, not an appendix.** Track 8 broke two results. The
ownership gap is two thirds size rather than ownership, and track 1's null is
underpowered rather than informative. Both writeups were rewritten afterwards
rather than defended. Attack A1 showed track 3's *magnitude* does not survive
dropping log-normality even though its direction does, so every statement of that
magnitude now carries the qualifier and `tools/check_claims.py` fails the build
if the qualifier is deleted.

**Claims cannot drift.** `tools/check_claims.py` pairs every figure quoted in
this README, FINDINGS.md and FALSIFICATION.md with the code that recomputes it,
and also fails on missing hedges and on overclaiming language. A test feeds it a
deliberately corrupted README to demonstrate that the guard can fail.

## What is missing, stated once

- **No spending variable anywhere.** FERC Form 1 is unreachable and the three
  Form 1 repositories on GitHub ship extraction code, not data. Track 1
  regresses physical **deployment** instead and says so at the top of the module;
  track 4's vegetation-management question is marked BLOCKED rather than proxied.
- **No weather severity index.** So track 2 cannot separate weather severity from
  classification, which is the question it was scoped to answer.
- **No daily SAIDI, anywhere, at national scale.** Which is why track 3 inverts
  an identity instead of recomputing thresholds, and why its result is
  model-implied rather than measured.
- **Four filing years with a seven-year hole** (2013-2015, 2022). No year-by-year
  trajectory is estimable.

Search record and mirror licences: [docs/DATA_ACCESS.md](docs/DATA_ACCESS.md).

## Layout

```
blinkrate/
  shared/ingest.py              EIA-861 harmonised across two file layouts
  shared/reliability_metrics.py MED engine, tunable beta, closed form
  shared/finite_sample.py       simulated median-realization calibration
  track1_investment.py          capital deployment vs reliability + variance decomp
  track2_weather_split.py       MED gap trend on a balanced panel
  track3_med_sensitivity.py     headline: threshold sweep, bunching, standard choice
  track4_cause_exclusions.py    BLOCKED (FERC); loss-of-supply substituted
  track5_undergrounding.py      breakeven model, literature parameters
  track6_ownership.py           IOU / co-op / municipal stratification
  track7_validation.py          engine and source-data checks
  track8_falsification.py       six attacks on the above
  run_all.py
data/raw/                       vendored EIA-861 (US Gov, public domain)
docs/derivation.md              the exclusion identity
docs/DATA_ACCESS.md             provenance, licences, what is blocked
tools/check_claims.py           drift and overclaim guard
tools/utility_profile.py        run one utility's filed numbers through the engine
```

## Data

EIA Form 861, filing years 2013, 2014, 2015 and 2022. US federal government work,
public domain, retrieved through GitHub mirrors because eia.gov is unreachable
from the build environment. Mirror attribution in [NOTICE](NOTICE).

## Citing

See [CITATION.cff](CITATION.cff). MIT licensed.
