# Data access: what is here, where it came from, what is missing

## Reachable

Network egress permits `github.com`, `raw.githubusercontent.com`,
`codeload.github.com` and the package registries. It does not permit `eia.gov`,
`ferc.gov`, `noaa.gov`, `emp.lbl.gov` or state utility commission sites, all of
which return 403 at the proxy.

Every dataset in `data/raw/` is a US federal government work (EIA Form 861),
retrieved through a GitHub mirror because the primary source is unreachable.
The data is public domain; the mirrors are the retrieval path, not the rights
holder.

| File | Years | Mirror | Mirror license |
|---|---|---|---|
| `Reliability_2013.csv`, `_2014`, `_2015` | 2013-2015 | `marcelMerchat/electricPowerReliability1` | none stated |
| `Sales_Ult_Cust_2013.csv`, `_2014`, `_2015` | 2013-2015 | `marcelMerchat/electricPowerReliability1` | none stated |
| `Reliability_2022.xlsx` | 2022 | `Dex947/distribution-reliability-outage-analytics` | MIT |
| `Advanced_Meters_2022.xlsx` | 2022 | same | MIT |
| `Distribution_Systems_2022.xlsx` | 2022 | same | MIT |
| `Frame_2022.xlsx` | 2022 | same | MIT |
| `Sales_Ult_Cust_2022.xlsx` | 2022 | same | MIT |

`data/calibration_med.npz` is generated, not downloaded. Rebuild it with
`python -m blinkrate.shared.finite_sample`.

## The panel this produces

Four filing years — 2013, 2014, 2015, 2022 — with a seven-year hole in the
middle. 3,854 utility-state-year rows load; 3,427 survive the analysis filter.
The gap is the single biggest limitation in the repo. It is why:

- track 1's investment regression is a 2022 cross-section, not a panel with lags;
- track 2's trend is four points with a jump, so a 2013-2022 change cannot be
  distinguished from a level shift somewhere in the missing years;
- nothing here estimates a year-by-year trajectory.

Searched for the missing years and did not find them. Repository search on
GitHub for `eia861`, `eia-861`, `SAIDI`, `SAIFI`, `IEEE 1366`, `annual electric
power industry report 861` and several variants returns 11 distinct repositories;
only the two mirrored above ship reliability data. Code search, which would find
a stray `Reliability_2019.xlsx` inside an unrelated repo, requires
authentication and there are no credentials in this environment.

## Genuinely missing

**FERC Form 1 (track 1 capex, track 4 vegetation management).** `ferc.gov` is
blocked. The three Form 1 repositories on GitHub —
`catalyst-cooperative/ferc1-data-release`, `catalyst-cooperative/rmi-ferc1-eia`,
`doig007/Form1Analysis` — were cloned and inspected. They contain extraction
scripts, schema documentation and blank form PDFs. All three download the data
from ferc.gov at runtime. Catalyst's PUDL distributes processed Form 1 through
Zenodo and S3, both blocked.

Consequence: **there is no spending variable anywhere in this repo.** Track 1
regresses physical deployment instead and says so at the top of the module.
Track 4 is marked BLOCKED rather than proxied.

**Outage cause codes (track 4).** EIA-861 has no cause-coded table. Causes are
published in state reliability filings, not federally. No national dataset was
found.

**Weather severity (track 2).** NOAA is blocked and no mirrored storm-severity
panel keyed to utility service territories was found. Track 2 therefore uses the
major-event-day gap as an internal indicator and cannot separate "more severe
weather" from "more days classified as major events" — which is precisely the
distinction the track was scoped to make. Stated in the module and in FINDINGS.

**Daily SAIDI series (track 3).** Not a proxy problem, a publication problem:
EIA-861 reports annual aggregates only, and no utility publishes daily SAIDI at
national scale. This is why track 3 inverts the exclusion identity rather than
recomputing thresholds. See `docs/derivation.md`.

## Track 5 literature parameters

Track 5 is a payback model rather than a measurement, and its inputs come from
published sources recorded inline in `PARAMS` in
`blinkrate/track5_undergrounding.py`: EEI and CPUC conversion cost ranges, the
LBNL ICE Calculator customer-interruption cost as restated in arXiv:2407.10773,
and reliability improvement estimates from both the engineering case-study
literature and the Larsen et al. (2020) econometric estimate. The disagreement
between those two literatures is the track's finding, not an inconvenience.
