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
| `Reliability_2016/2017/2018.xlsx` | 2016-2018 | `IMMM-SFA/electricity_entity_boundaries` | BSD 2-Clause |
| `Advanced_Meters_2016/2017/2018.xlsx` | 2016-2018 | same | BSD 2-Clause |
| `Distribution_Systems_2016/2017/2018.xlsx` | 2016-2018 | same | BSD 2-Clause |
| `Reliability_2022.xlsx` | 2022 | `Dex947/distribution-reliability-outage-analytics` | MIT |
| `Advanced_Meters_2022.xlsx` | 2022 | same | MIT |
| `Distribution_Systems_2022.xlsx` | 2022 | same | MIT |
| `Frame_2022.xlsx` | 2022 | same | MIT |
| `Sales_Ult_Cust_2022.xlsx` | 2022 | same | MIT |

`data/calibration_med.npz` is generated, not downloaded. Rebuild it with
`python -m blinkrate.shared.finite_sample`.

`data/daily/` is the one non-EIA dataset: per-snapshot customers-out counts for
two utilities, derived from public git-scraping archives of their outage maps
(PG&E 2019-2022 from `simonw/pge-outages-pre-2024`, Apache-2.0; FPL by county
2019-2023 from `simonw/disaster-data`, no licence stated, counts only). Its
README gives the pinned commits, the rebuild command
(`python tools/build_outage_snapshots.py`), the checksums a rebuild reproduces,
and what the series are not.

## The panel this produces

Seven filing years: 2013 through 2018, then 2022. 7,068 utility-state-year rows
load; 6,245 survive the analysis filter; 12 rows are genuine duplicate filings in
the 2014 source and are deduplicated on the larger customer count.

**This started as four years and the difference was substantial.** The first
version of this repository had 2013-2015 and 2022 only, a seven-year hole, and
three tracks that could not answer their own question because of it. Finding the
2016-2018 files closed most of the gap and changed real conclusions: it retracted
one published regression result, turned a point estimate into a range, and let
two previously unanswerable questions be answered. That is recorded in
FALSIFICATION.md rather than smoothed over.

What the remaining hole still costs: 2019-2021 are missing, so 2022 is a single
later observation rather than a continuation, and nothing here can date movement
after 2018.

### How they were found

The repository search that produced the 2013-2015 and 2022 mirrors found nothing
else. GitHub code search, which would locate a stray `Reliability_2019.xlsx`
inside an unrelated repository, requires authentication and there are no
credentials in this environment.

What worked instead was a web search for the filenames rather than the topic.
`IMMM-SFA/electricity_entity_boundaries` is a service-territory mapping project
from a multi-sector modelling group; the EIA-861 reliability files are incidental
inputs it happens to vendor, so no amount of searching for "SAIDI" or "reliability
analysis" would surface it. **If a dataset is unreachable, search for the file
name, not the subject.**

### A layout trap worth knowing before you use these files

The three vendored layouts disagree about nearly everything:

| years | format | header rows | column naming | Ownership / CAIDI |
|---|---|---|---|---|
| 2013-2015 | CSV | 2 | "SAIDI With MED" | absent |
| 2016-2018 | XLSX | 2 | "SAIDI With MED" | present |
| 2022 | XLSX | 3 | "SAIDI (minutes per year)" | present |

Reading by column name works for 2016-2018 and then silently fails on 2022,
where every metric column was renamed. Reading by position works for all three,
because EIA changed the labels but not the order. 2022 also inserted an Ownership
column into the Advanced Meters file, shifting every column after it by one.

Worse, all three layouts place the IEEE-standard block and the Other-standard
block side by side with identical column names, so even within one file a
header-based read keeps one and drops the other without complaint.

## Genuinely missing

**FERC Form 1 (track 1 capex, track 4 vegetation management).** `ferc.gov` is
blocked. The three Form 1 repositories on GitHub
(`catalyst-cooperative/ferc1-data-release`, `catalyst-cooperative/rmi-ferc1-eia`,
`doig007/Form1Analysis`) were cloned and inspected. They contain extraction
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
weather" from "more days classified as major events", which is precisely the
distinction the track was scoped to make. Stated in the module and in FINDINGS.

**Daily SAIDI series (track 3), partly found.** Not a proxy problem, a
publication problem: EIA-861 reports annual aggregates only, and no utility
publishes daily SAIDI at national scale. This is why track 3 inverts an identity
instead of recomputing thresholds.

What was found, late: two utilities' outage maps archived by git scraping, a
practice where a scheduled job commits each fetched snapshot to a public
repository, so the commit history is a time series. A web search for daily
outage data surfaced a 2019 blog post about scraping PG&E's outage map into git,
which led to `simonw/pge-outages-pre-2024` (PG&E, 2019-2022). The scraper's
sibling data repository, `simonw/disaster-data`, turned out to hold a
county-level FPL history (2019-2023) that nothing in its name or description
advertises. Both are vendored in `data/daily/` and tested in attack A14. They
are outage-map estimates for two utilities, not reported SAIDI and not national,
so the gap is narrowed rather than closed. The lesson generalizes the one above:
**data that no publisher releases may still exist as the commit history of
someone's scraper.**

The closest public substitute at national scale is ORNL's EAGLE-I county outage record
(Brelsford et al., Scientific Data 2024, DOI 10.1038/s41597-024-03095-5):
customers out per county every 15 minutes, 2014 to 2022. It is distributed
through Globus and Figshare at 1.1 to 1.2 GB a year, neither reachable from the
build environment and too large to vendor. The GitHub repository
`SC-Lab-Go/SMCDC-EAGLE-I` documents the files but does not host them.
`tools/daily_tail_test.py` reads an EAGLE-I file directly for anyone who has it.
Two caveats travel with the data: county customers-out approximates
customer-minutes rather than measuring SAIDI, and EAGLE-I omits zero rows without
distinguishing them from collection gaps.

**The 2019-2021 filings.** Catalyst Cooperative's PUDL publishes the EIA-861
reliability table as `core_eia861__yearly_reliability`, including these years,
through S3, Kaggle and Zenodo rather than GitHub. Searching the raw workbook file
names (`Reliability_2019.xlsx` and so on), the method that found 2016-2018, turned
up no GitHub mirror. PUDL issue 4907 reports a column swap affecting its 2024 rows
only; anyone loading through PUDL should check the column order against EIA's
raw workbook, which is what `ingest.py`'s position-based column map exists to do.

## Track 5 literature parameters

Track 5 is a payback model rather than a measurement, and its inputs come from
published sources recorded inline in `PARAMS` in
`blinkrate/track5_undergrounding.py`: EEI and CPUC conversion cost ranges, the
LBNL ICE Calculator customer-interruption cost as restated in arXiv:2407.10773,
and reliability improvement estimates from both the engineering case-study
literature and the Larsen et al. (2020) econometric estimate. The disagreement
between those two literatures is the track's finding, not an inconvenience.
