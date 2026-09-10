"""Track 4 - vegetation management spend vs cause-specific outages: BLOCKED.

WHAT WAS WANTED. Vegetation management spending is a FERC Form 1 line item;
outage cause codes come from utility outage management systems. Pair them, and
you get a much sharper question than track 1's aggregate: does trimming trees
reduce tree-caused outages specifically.

WHY IT IS BLOCKED, WITH THE SEARCH RECORD.
  - ferc.gov returns 403 at the egress proxy, as do eia.gov and the utility
    regulatory sites. Only github, raw.githubusercontent, codeload and the
    package registries are reachable.
  - The three FERC Form 1 repositories on GitHub that surface for this
    (catalyst-cooperative/ferc1-data-release, catalyst-cooperative/rmi-ferc1-eia,
    doig007/Form1Analysis) contain extraction code, schema notes and blank form
    PDFs. None ships the data; all of them download it from ferc.gov at runtime.
  - EIA-861 has no cause-coded outage table at all. Outage causes are published
    per utility in state reliability filings, not federally.

There is no honest proxy for vegetation spending in the reachable data. Circuit
counts do not measure trimming; AMI penetration does not measure trimming.
Rather than invent one, this module reports the one cause-specific exclusion
that EIA-861 does publish, which is a different question with an honest label:

LOSS OF SUPPLY. Under the IEEE block, utilities report a third SAIDI variant with
loss-of-supply events removed - outages that originate upstream of the
distribution system, on transmission or generation. It is a cause-attributable
carve-out, it is discretionary in the same way major-event-day classification is,
and nobody looks at it. This module measures how much it removes and who uses it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .shared import ingest
from .shared.io import save_results

BLOCKER = (
    "FERC Form 1 vegetation management spending and utility outage cause codes "
    "are both unreachable: ferc.gov blocked, no mirrored Form 1 dataset on "
    "GitHub, no cause-coded outage table in EIA-861. Track 4 as scoped is not "
    "answerable from public data reachable here, and is not proxied."
)


def los_usage() -> dict:
    """Who reports the loss-of-supply variant, and how much does it remove?

    The LOS column is only collected in the IEEE block, so the denominator is
    IEEE reporters. `saidi_no_los` is SAIDI with major event days INCLUDED but
    loss-of-supply events removed, so it is compared against saidi_with.
    """
    df = ingest.analysis_sample()
    ieee = df[df["standard"] == "IEEE"].copy()
    has = ieee["saidi_no_los"].notna() & (ieee["saidi_with"] > 0)
    d = ieee[has].copy()

    d["los_retained"] = (d["saidi_no_los"] / d["saidi_with"]).clip(upper=None)
    valid = d[(d["los_retained"] >= 0) & (d["los_retained"] <= 1)]

    by_year = {
        int(y): {
            "n_ieee": int((ieee["year"] == y).sum()),
            "n_reporting_los": int((d["year"] == y).sum()),
            "share_reporting_los": float((d["year"] == y).sum()
                                         / max((ieee["year"] == y).sum(), 1)),
            "median_los_retained": float(
                valid.loc[valid["year"] == y, "los_retained"].median()),
        }
        for y in sorted(ieee["year"].unique())
    }

    by_own = {
        str(k): {
            "n": int(len(sub)),
            "median_los_retained": float(sub["los_retained"].median()),
            "share_los_removes_nothing": float((sub["los_retained"] >= 1 - 1e-9).mean()),
        }
        for k, sub in valid.groupby("ownership_class") if len(sub) >= 20
    }

    # Stacking the two carve-outs: what survives both MED and LOS removal?
    stacked = valid.copy()
    stacked["both_retained"] = (
        stacked["retained_share"] * stacked["los_retained"]).clip(0, 1)

    return {
        "n_ieee_rows": int(len(ieee)),
        "n_reporting_los": int(len(d)),
        "share_of_ieee_reporting_los": float(len(d) / max(len(ieee), 1)),
        "n_valid": int(len(valid)),
        "median_los_retained_share": float(valid["los_retained"].median()),
        "mean_los_retained_share": float(valid["los_retained"].mean()),
        "share_where_los_removes_nothing": float(
            (valid["los_retained"] >= 1 - 1e-9).mean()),
        "customer_weighted_los_retained": float(
            np.average(valid["los_retained"], weights=valid["customers"])),
        "by_year": by_year,
        "by_ownership": by_own,
        "stacked_med_and_los": {
            "median_combined_retained": float(stacked["both_retained"].median()),
            "note": ("multiplicative approximation: EIA does not publish a "
                     "both-removed variant, so this assumes the two carve-outs "
                     "are independent, which they are not for storm events "
                     "that take out transmission"),
        },
    }


def run(save: bool = True) -> dict:
    out = {"status": "BLOCKED", "blocker": BLOCKER,
           "substituted_analysis": "loss-of-supply exclusion usage",
           "los": los_usage()}
    if save:
        save_results("track4_cause_exclusions", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
