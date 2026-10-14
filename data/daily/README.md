# Daily outage data: two utilities' outage maps

EIA-861 publishes annual reliability aggregates only, so nothing in `data/raw/`
can test IEEE 1366's assumption that daily SAIDI is log-normal. These two files
can. Each row is one snapshot of a utility's public outage map, archived by "git
scraping": a scheduled job fetched the map every ten minutes or so and committed
it to a public repository whenever it changed, so each commit's time and content
record how many customers were out at that moment.

| File | Utility | Span | Snapshots | Columns |
|---|---|---|---|---|
| `pge_outage_map_snapshots.csv` | Pacific Gas & Electric (CA) | 2019-06-10 to 2022-04-21 | 66,011 | `t`, `customers_out`, `psps`, `planned` |
| `fpl_outage_map_snapshots.csv` | Florida Power & Light (FL), 35 counties | 2019-09-02 to 2023-01-31 | 89,310 | `t`, `customers_out`, `customers_served` |

`t` is the commit time in Unix seconds (UTC). `customers_out` is the map's total
at that snapshot. For PG&E, `psps` is the part attributed to Public Safety Power
Shutoffs and `planned` the part attributed to scheduled maintenance or
vegetation clearing, both identified by the cause text PG&E's map attached to
each outage. For FPL, both columns are totals over the 35 counties of FPL's
legacy territory, which the page lists in every complete snapshot, and
`customers_served` is the page's own count of customers served there.

## Where they come from

| File | Archive | Pinned commit | Licence |
|---|---|---|---|
| PG&E | `github.com/simonw/pge-outages-pre-2024`, file `pge-outages.json` | `d1561539277a42890b85bb57f97f5bc8598c5454` | Apache-2.0 |
| FPL | `github.com/simonw/disaster-data`, file `florida/fpl-county-outages.json` | `6ab407fc8a2e42809c6fa80b57b992b40e0895bf` | none stated |

Both archives were built by Simon Willison. The FPL archive carries no licence
file. What is redistributed here is only the per-snapshot customer counts, which
are facts, not the archived documents themselves.

Rebuild both files with `python tools/build_outage_snapshots.py`. It clones the
archives, streams every committed version of the file up to the pinned commit,
and sums the counts. Rebuilt from fresh clones, the output is byte-identical:

```
e6d4522eafd8eb47ec8a6900cd1bc022614596fbbfae5e7024236d1096a18bc7  pge_outage_map_snapshots.csv
2fd5863b7a5b1521630ce32eced8cdb97cc03fdeb177a988ae44af2846be9deb  fpl_outage_map_snapshots.csv
```

## What these are, and are not

**Not reported SAIDI.** Customers out on an outage map is an operational
estimate refreshed every few minutes, not the interruption record a utility
reports under IEEE 1366. It misses momentary interruptions and can include
customers whose outage the utility later excludes. For FPL 2022, the one
utility-year with both a filing and a near-complete year of map data, the map's
annual total runs above what FPL filed, by more on ordinary days than on major
event days (attack A14 reports both ratios). Use these series for the shape of
daily outage burden and for how the exclusion rule acts on it, not for the level
of reported SAIDI.

**Not continuous.** Both scrapers stopped for weeks or months at a time. The
PG&E archive is observed for about 21 of its 34 months and the FPL archive for
about 29 of 41. `blinkrate/shared/daily.py` treats any silence longer than three
hours as unobserved and keeps a day only if at least 90% of it was observed;
attack A14 varies both rules.

**Not complete territories.** The FPL series covers FPL's legacy territory, 35
counties and about 5.2 million customers. The page also listed Gulf Power's
eight northwest Florida counties for ten days in September 2019, and two
snapshots are truncated pages; the build sums only the 35 counties and skips
those two, so the territory is the same in every row. FPL's EIA-861 filing
absorbed the former Gulf Power from 2022, so the filing covers more territory
than the series does.

**Not representative.** Two large investor-owned utilities in two extreme-weather
states, in years that include PG&E's 2019 shutoffs and Hurricane Ian. A result on
these series is a result about these utilities.
