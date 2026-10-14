#!/usr/bin/env python3
"""Rebuild data/daily/ from two public git-scraping archives of utility outage maps.

    python tools/build_outage_snapshots.py               # clones both archives
    python tools/build_outage_snapshots.py --cache DIR   # reuse clones in DIR

Two outage maps were archived by committing a snapshot to git every ten minutes
or so, a practice known as git scraping: each commit's timestamp and content
record how many customers were out at that moment. This tool streams every
committed version of one file per archive, up to a pinned commit, and writes one
row per snapshot with the customers-out totals. Nothing is interpolated or
smoothed here. Integration into daily customer-minutes happens in
blinkrate/shared/daily.py, where it is tested.

  PG&E  github.com/simonw/pge-outages-pre-2024, pge-outages.json, Apache-2.0.
        One record per outage, with estCustAffected and a cause string. Public
        Safety Power Shutoffs and planned work are identified by the cause text
        PG&E's map used for them (see PSPS_PREFIX and PLANNED below).
  FPL   github.com/simonw/disaster-data, florida/fpl-county-outages.json. No
        licence file; the snapshots are counts of customers, which are facts,
        and only those counts are redistributed here. One record per county,
        with Customers Out and Customers Served. The page lists FPL's 35
        legacy-territory counties throughout, but for ten days in September
        2019 it also listed Gulf Power's eight northwest Florida counties, and
        two snapshots are truncated pages. Only the 35 counties are summed, so
        the territory is the same in every row, and a snapshot missing any of
        them is skipped.

Rows keep every commit, including ones whose totals did not change, because the
gap between commits is how the integration step tells a quiet hour from an
hour the scraper was down. Output is deterministic: the same pinned commits give
byte-identical files.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "daily"

PSPS_PREFIX = "To protect public safety"
PLANNED = ("scheduled maintenance work", "We are clearing vegetation")

# The counties FPL's page lists in every complete snapshot: its legacy
# territory. Gulf Power's counties appear only between 11 and 21 September 2019.
FPL_COUNTIES = (
    "Alachua", "Baker", "Bradford", "Brevard", "Broward", "Charlotte", "Clay",
    "Collier", "Columbia", "De Soto", "Duval", "Flagler", "Glades", "Hardee",
    "Hendry", "Highlands", "Indian River", "Lee", "Manatee", "Martin",
    "Miami-Dade", "Monroe", "Nassau", "Okeechobee", "Orange", "Osceola",
    "Palm Beach", "Putnam", "Sarasota", "Seminole", "St Johns", "St Lucie",
    "Suwannee", "Union", "Volusia")

ARCHIVES = {
    "pge": {
        "url": "https://github.com/simonw/pge-outages-pre-2024",
        "commit": "d1561539277a42890b85bb57f97f5bc8598c5454",
        "path": "pge-outages.json",
        "out": "pge_outage_map_snapshots.csv",
        "columns": ["t", "customers_out", "psps", "planned"],
    },
    "fpl": {
        "url": "https://github.com/simonw/disaster-data",
        "commit": "6ab407fc8a2e42809c6fa80b57b992b40e0895bf",
        "path": "florida/fpl-county-outages.json",
        "out": "fpl_outage_map_snapshots.csv",
        "columns": ["t", "customers_out", "customers_served"],
    },
}


def _count(value) -> int:
    """Counts arrive as ints, numeric strings, '1,234' strings or nothing."""
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0


def pge_row(records: list) -> list[int]:
    out = psps = planned = 0
    for r in records:
        n = _count(r.get("estCustAffected"))
        cause = r.get("cause") or ""
        out += n
        if cause.startswith(PSPS_PREFIX):
            psps += n
        elif any(p in cause for p in PLANNED):
            planned += n
    return [out, psps, planned]


def fpl_row(doc: dict) -> list[int] | None:
    """Totals over FPL_COUNTIES, or None if the page lacks any of them."""
    rows = {r["County Name"]: r for r in doc["outages"]}
    if any(c not in rows for c in FPL_COUNTIES):
        return None
    return [sum(_count(rows[c]["Customers Out"]) for c in FPL_COUNTIES),
            sum(_count(rows[c]["Customers Served"]) for c in FPL_COUNTIES)]


def versions(repo: Path, commit: str, path: str):
    """(commit time, blob bytes) for every version of path up to commit, oldest first."""
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--reverse", "--raw", "--no-abbrev",
         "--format=C %ct", commit, "--", path],
        capture_output=True, text=True, check=True).stdout
    found, t = [], None
    for line in log.splitlines():
        if line.startswith("C "):
            t = int(line.split()[1])
        elif line.startswith(":"):
            meta, name = line.split("\t", 1)
            fields = meta.split()
            if name == path and fields[4] != "D":
                found.append((t, fields[3]))
    cat = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for t, blob in found:
        cat.stdin.write(blob.encode() + b"\n")
        cat.stdin.flush()
        size = int(cat.stdout.readline().split()[2])
        data = cat.stdout.read(size)
        cat.stdout.read(1)
        yield t, data
    cat.stdin.close()
    cat.wait()


def build(key: str, repo: Path) -> Path:
    spec = ARCHIVES[key]
    subprocess.run(["git", "-C", str(repo), "cat-file", "-e", spec["commit"] + "^{commit}"],
                   check=True)
    rows, skipped = [], 0
    for t, data in versions(repo, spec["commit"], spec["path"]):
        doc = json.loads(data)
        totals = pge_row(doc) if key == "pge" else fpl_row(doc)
        if totals is None:
            skipped += 1
            continue
        rows.append([t] + totals)
    # Commit times come from the scraper's clock. Sort stably and keep the last
    # snapshot recorded at any one second, so time never runs backwards.
    rows.sort(key=lambda r: r[0])
    dedup = {}
    for r in rows:
        dedup[r[0]] = r
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / spec["out"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(spec["columns"])
        w.writerows(dedup[t] for t in sorted(dedup))
    print(f"{key}: {len(rows)} snapshots ({skipped} incomplete skipped), "
          f"{len(dedup)} distinct times -> {path}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path,
                    help="directory holding (or receiving) bare clones of the archives")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        base = args.cache or Path(tmp)
        base.mkdir(parents=True, exist_ok=True)
        for key, spec in ARCHIVES.items():
            repo = base / f"{key}.git"
            if not repo.exists():
                subprocess.run(["git", "clone", "--quiet", "--bare", spec["url"], str(repo)],
                               check=True)
            build(key, repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
