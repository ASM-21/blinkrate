"""Track 2 - is the reliability trend a weather story or a performance story?

The mechanism the spec wanted is already in the raw data: EIA-861 reports SAIDI
both with and without major event days, so the gap between the two series is the
part of reported outage time that the utility attributes to major events. If
reliability is deteriorating because of weather, the with-MED series should
worsen faster than the without-MED series and the gap should widen. If it is
deteriorating because of utility performance, both should move together.

WHAT IS MISSING. There is no external weather severity index in this repo.
NOAA is blocked at the egress proxy and no mirrored storm-severity panel keyed
to utility service territories was found, so the correlation between the MED gap
and an independent weather measure - the second half of the track as scoped - is
not computed. The gap is used as an internal indicator only, which means this
track cannot distinguish "more severe weather" from "more days classified as
major events". Those are exactly the two explanations the repo exists to keep
apart, so read the result as bounding the question, not settling it.

COMPOSITION. The available filing years are 2013, 2014, 2015 and 2022, and the
set of reporting utilities changes across them. Every trend below is computed on
the balanced panel of utility-states present in all four years, because on the
unbalanced sample entry and exit alone move the fleet average.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .shared import ingest
from .shared.io import PALETTE, save_figure, save_results, style_axes

YEARS = (2013, 2014, 2015, 2022)


def balanced_panel() -> pd.DataFrame:
    df = ingest.analysis_sample()
    df = df[df["year"].isin(YEARS)]
    n = df.groupby("utility_state")["year"].nunique()
    keep = n[n == len(YEARS)].index
    return df[df["utility_state"].isin(keep)].copy()


def _wavg(sub: pd.DataFrame, col: str) -> float:
    return float(np.average(sub[col], weights=sub["customers"]))


def trend_table(df: pd.DataFrame) -> dict:
    rows = {}
    for y, sub in df.groupby("year"):
        rows[int(y)] = {
            "n": int(len(sub)),
            "saidi_with_cw": _wavg(sub, "saidi_with"),
            "saidi_without_cw": _wavg(sub, "saidi_without"),
            "med_gap_cw": _wavg(sub, "excluded_minutes"),
            "median_retained_share": float(sub["retained_share"].median()),
            "share_zero_exclusion": float((sub["retained_share"] >= 1 - 1e-9).mean()),
            "saifi_with_cw": _wavg(sub.dropna(subset=["saifi_with"]), "saifi_with"),
        }
    first, last = min(rows), max(rows)
    growth = {
        f"pct_change_{first}_{last}": {
            k: float(100 * (rows[last][k] / rows[first][k] - 1))
            for k in ("saidi_with_cw", "saidi_without_cw", "med_gap_cw")
        }
    }
    return {"by_year": rows, **growth}


def within_utility_decomposition(df: pd.DataFrame) -> dict:
    """Same question, utility by utility, so composition cannot drive it.

    For each utility-state present in both endpoints, the change in with-MED
    SAIDI is split into the change in the retained (non-major-event) part and
    the change in the excluded part.
    """
    a = df[df["year"] == min(YEARS)].set_index("utility_state")
    b = df[df["year"] == max(YEARS)].set_index("utility_state")
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]

    d_with = b["saidi_with"] - a["saidi_with"]
    d_without = b["saidi_without"] - a["saidi_without"]
    d_excluded = b["excluded_minutes"] - a["excluded_minutes"]
    w = b["customers"]

    tot = float(np.average(d_with, weights=w))
    return {
        "n_utility_states": int(len(common)),
        "mean_change_saidi_with_cw": tot,
        "mean_change_saidi_without_cw": float(np.average(d_without, weights=w)),
        "mean_change_excluded_cw": float(np.average(d_excluded, weights=w)),
        "share_of_change_from_excluded_part": (
            float(np.average(d_excluded, weights=w) / tot) if tot != 0 else np.nan),
        "median_change_retained_share": float(
            (b["retained_share"] - a["retained_share"]).median()),
        "share_of_utilities_worsening_with_med": float((d_with > 0).mean()),
        "share_of_utilities_worsening_without_med": float((d_without > 0).mean()),
    }


def exclusion_entry(df: pd.DataFrame) -> dict:
    """Did utilities that reported zero exclusion in 2013 start excluding later?

    A pure weather story does not predict this; a methodology-adoption story
    does. It is the sharpest thing this track can say without a weather index.
    """
    a = df[df["year"] == 2013].set_index("utility_state")
    b = df[df["year"] == 2022].set_index("utility_state")
    common = a.index.intersection(b.index)
    za = a.loc[common, "retained_share"] >= 1 - 1e-9
    zb = b.loc[common, "retained_share"] >= 1 - 1e-9
    return {
        "n": int(len(common)),
        "zero_exclusion_2013": float(za.mean()),
        "zero_exclusion_2022": float(zb.mean()),
        "started_excluding": float((za & ~zb).mean()),
        "stopped_excluding": float((~za & zb).mean()),
        "net_entry_into_exclusion": float((za & ~zb).mean() - (~za & zb).mean()),
    }


def _fig(df: pd.DataFrame, tt: dict) -> None:
    import matplotlib.pyplot as plt
    yrs = sorted(tt["by_year"])
    w = [tt["by_year"][y]["saidi_with_cw"] for y in yrs]
    wo = [tt["by_year"][y]["saidi_without_cw"] for y in yrs]
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    ax.plot(yrs, w, marker="o", color=PALETTE["with_med"], lw=2.2,
            label="reported with major event days")
    ax.plot(yrs, wo, marker="o", color=PALETTE["without_med"], lw=2.2,
            label="reported without major event days")
    ax.fill_between(yrs, wo, w, color=PALETTE["accent"], alpha=0.18,
                    label="excluded as major events")
    ax.set_xticks(yrs)
    ax.set_xlabel("EIA-861 filing year")
    ax.set_ylabel("customer-weighted SAIDI (min/yr)")
    ax.set_title("Balanced panel: the gap is doing the moving", loc="left",
                 fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax)
    save_figure(fig, "track2_med_gap_trend")


def run(save: bool = True) -> dict:
    df = balanced_panel()
    tt = trend_table(df)
    out = {
        "blocker": ("no external weather severity index: NOAA blocked, no mirrored "
                    "storm panel keyed to service territories found. The MED gap "
                    "cannot be separated into weather severity vs classification."),
        "balanced_panel_utility_states": int(df["utility_state"].nunique()),
        "trend": tt,
        "within_utility": within_utility_decomposition(df),
        "exclusion_entry": exclusion_entry(df),
    }
    if save:
        _fig(df, tt)
        save_results("track2_weather_split", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
