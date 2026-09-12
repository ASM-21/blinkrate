"""Track 2 - is the reliability trend weather, or is it classification?

THE QUESTION. Reported SAIDI has been getting worse. Two explanations compete:
storms are worse, or more days are being classified as major events and moved
out of the headline number. They have opposite policy implications and the data
that separates them cleanly does not exist publicly.

WHAT THE DATA CAN DO. EIA-861 reports SAIDI twice, with and without major event
days, so the gap between the two series is the portion a utility attributes to
major events. If weather is driving the trend, the with-MED series should worsen
faster than the without-MED series and the gap should widen. If everyday
distribution performance is driving it, both should move together.

WHAT IT CANNOT DO, AND THIS IS THE LIMIT OF THE TRACK. There is no external
weather severity index here. NOAA is blocked and no mirrored storm panel keyed
to utility service territories was found. A widening gap is equally consistent
with worse storms and with more aggressive classification. This track bounds the
question; it does not settle it. The one place it gets traction is that some
movements are discrete methodology changes rather than weather - a utility going
from reporting no exclusion at all to reporting some has changed how it
measures, not what the sky did.

WHAT CHANGED WITH THE 2016-2018 FILINGS. The earlier version of this track had
four filing years with a seven-year hole and could only compare endpoints. There
are now six consecutive years, 2013 through 2018, plus 2022. That allows the
question the earlier version could not ask: is the growth in the excluded
portion a gradual drift or a step change, and does 2022 sit on the 2013-2018
trend or above it?

COMPOSITION. Every trend below is computed on utilities present in every year of
the window. On an unbalanced sample, entry and exit alone move the fleet
average.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .shared import ingest
from .shared.io import PALETTE, save_figure, save_results, style_axes

ALL_YEARS = (2013, 2014, 2015, 2016, 2017, 2018, 2022)
CONSECUTIVE = (2013, 2014, 2015, 2016, 2017, 2018)


def balanced_panel(years=ALL_YEARS) -> pd.DataFrame:
    df = ingest.analysis_sample()
    df = df[df["year"].isin(years)]
    n = df.groupby("utility_state")["year"].nunique()
    return df[df["utility_state"].isin(n[n == len(years)].index)].copy()


def _wavg(sub: pd.DataFrame, col: str) -> float:
    s = sub.dropna(subset=[col, "customers"])
    return float(np.average(s[col], weights=s["customers"]))


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
        }
    first, last = min(rows), max(rows)
    return {
        "by_year": rows,
        f"pct_change_{first}_{last}": {
            k: float(100 * (rows[last][k] / rows[first][k] - 1))
            for k in ("saidi_with_cw", "saidi_without_cw", "med_gap_cw")
        },
    }


def gradual_or_step(df: pd.DataFrame) -> dict:
    """Is the excluded portion drifting up, or did it jump?

    Fits a linear trend to the customer-weighted major-event gap over the six
    consecutive years, then asks whether 2022 sits on that line. A gradual
    weather-and-methodology drift predicts 2022 near the extrapolation; a step
    predicts it well off.

    Six points is a short series and the trend test is reported with that in
    mind: the slope's confidence interval is wide by construction and the
    extrapolation four years past the last observation is the weakest thing in
    this module.
    """
    cons = balanced_panel(CONSECUTIVE)
    tt = trend_table(cons)["by_year"]
    yrs = np.array(sorted(tt))
    gap = np.array([tt[y]["med_gap_cw"] for y in yrs])
    without = np.array([tt[y]["saidi_without_cw"] for y in yrs])

    fit_gap = stats.linregress(yrs, gap)
    fit_without = stats.linregress(yrs, without)

    # 2022 on the panel balanced across ALL years, so the same utilities
    full = balanced_panel(ALL_YEARS)
    full_tt = trend_table(full)["by_year"]
    obs_2022 = full_tt[2022]["med_gap_cw"]
    # re-fit the trend on the all-year balanced panel so the comparison is
    # like-for-like rather than across two different utility sets
    yrs_f = np.array([y for y in sorted(full_tt) if y != 2022])
    gap_f = np.array([full_tt[y]["med_gap_cw"] for y in yrs_f])
    fit_f = stats.linregress(yrs_f, gap_f)
    pred_2022 = fit_f.intercept + fit_f.slope * 2022
    resid_sd = float(np.std(gap_f - (fit_f.intercept + fit_f.slope * yrs_f), ddof=2))

    return {
        "consecutive_years": list(CONSECUTIVE),
        "n_utility_states_consecutive": int(cons["utility_state"].nunique()),
        "gap_slope_min_per_year": float(fit_gap.slope),
        "gap_slope_p": float(fit_gap.pvalue),
        "gap_r2": float(fit_gap.rvalue ** 2),
        "without_med_slope_min_per_year": float(fit_without.slope),
        "without_med_slope_p": float(fit_without.pvalue),
        "without_med_r2": float(fit_without.rvalue ** 2),
        "gap_2013": float(gap[0]), "gap_2018": float(gap[-1]),
        "extrapolation": {
            "predicted_2022_gap": float(pred_2022),
            "observed_2022_gap": float(obs_2022),
            "residual": float(obs_2022 - pred_2022),
            "residual_in_pre_2022_sd": float((obs_2022 - pred_2022) / resid_sd)
            if resid_sd > 0 else np.nan,
            "caveat": ("six fitted points extrapolated four years; treat the "
                       "residual as descriptive, not as a test"),
        },
    }


def within_utility_decomposition(df: pd.DataFrame, first: int, last: int) -> dict:
    """Utility by utility, so composition cannot drive it."""
    a = df[df["year"] == first].set_index("utility_state")
    b = df[df["year"] == last].set_index("utility_state")
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]

    d_with = b["saidi_with"] - a["saidi_with"]
    d_without = b["saidi_without"] - a["saidi_without"]
    d_excluded = b["excluded_minutes"] - a["excluded_minutes"]
    w = b["customers"]
    tot = float(np.average(d_with, weights=w))

    return {
        "span": f"{first} to {last}",
        "n_utility_states": int(len(common)),
        "mean_change_saidi_with_cw": tot,
        "mean_change_saidi_without_cw": float(np.average(d_without, weights=w)),
        "mean_change_excluded_cw": float(np.average(d_excluded, weights=w)),
        "share_of_change_from_excluded_part": (
            float(np.average(d_excluded, weights=w) / tot) if tot else np.nan),
        "unweighted_share_from_excluded": (
            float(d_excluded.mean() / d_with.mean()) if d_with.mean() else np.nan),
        "share_of_utilities_worsening_with_med": float((d_with > 0).mean()),
        "share_of_utilities_worsening_without_med": float((d_without > 0).mean()),
    }


def exclusion_entry(df: pd.DataFrame) -> dict:
    """Utilities moving into and out of using the exclusion at all.

    A pure weather story does not predict this. Reported per year so a drift can
    be told apart from a jump.
    """
    by_year = {
        int(y): float((sub["retained_share"] >= 1 - 1e-9).mean())
        for y, sub in df.groupby("year")
    }
    first, last = min(by_year), max(by_year)
    a = df[df["year"] == first].set_index("utility_state")["retained_share"]
    b = df[df["year"] == last].set_index("utility_state")["retained_share"]
    common = a.index.intersection(b.index)
    za, zb = a.loc[common] >= 1 - 1e-9, b.loc[common] >= 1 - 1e-9
    yrs = np.array(sorted(by_year))
    fit = stats.linregress(yrs, [by_year[y] for y in yrs])
    return {
        "share_zero_exclusion_by_year": by_year,
        "n": int(len(common)),
        "started_excluding": float((za & ~zb).mean()),
        "stopped_excluding": float((~za & zb).mean()),
        "net_entry_into_exclusion": float((za & ~zb).mean() - (~za & zb).mean()),
        "trend_pct_points_per_year": float(100 * fit.slope),
        "trend_p": float(fit.pvalue),
    }


# US states and territories affected by the 2017 Atlantic hurricane season's
# major landfalls: Harvey (TX, LA), Irma (FL, GA, SC), Maria (PR, VI), Nate
# (LA, MS, AL), plus NC on Irma's inland track. This list comes from the storm
# tracks, NOT from the reliability data. It is fixed before looking at which
# states moved, and it is applied unchanged to every year transition below so
# that 2017 has to distinguish itself rather than being selected.
HURRICANE_2017_STATES = ("TX", "LA", "FL", "GA", "SC", "PR", "VI", "MS", "AL", "NC")


def spike_geography(df: pd.DataFrame) -> dict:
    """Is the excluded portion moving where the storms were?

    The closest thing to a weather test available without a severity index. For
    every consecutive year transition it compares the customer-weighted change
    in excluded minutes INSIDE the hurricane-affected states against the change
    everywhere else, and does the same for the everyday (non-excluded) series.

    A note on the statistic, because the obvious one does not work. Expressing a
    group's contribution as a share of the fleet's NET change is unusable here:
    the net change is near zero in several transitions, so the share blows up to
    hundreds or thousands of percent and encodes nothing. Comparing group means
    in minutes is well defined whatever the net change does, and is directly
    readable.

    The logic is a placebo design. The state list is fixed from the 2017 storm
    tracks and applied unchanged to every transition. If those states move in
    every year, the list is just picking up big or storm-prone states generally.
    If they move only in the year the storms happened, and their everyday series
    stays flat while their excluded series jumps, that is the exclusion doing the
    job it was designed to do.
    """
    b = balanced_panel(ALL_YEARS)
    years = sorted(b["year"].unique())
    rows = {}
    for first, last in zip(years[:-1], years[1:]):
        a = b[b["year"] == first].set_index("utility_state")
        z = b[b["year"] == last].set_index("utility_state")
        common = a.index.intersection(z.index)
        d = pd.DataFrame({
            "state": a.loc[common, "state"],
            "cust": z.loc[common, "customers"],
            "d_excluded": (z.loc[common, "excluded_minutes"]
                           - a.loc[common, "excluded_minutes"]),
            "d_without": (z.loc[common, "saidi_without"]
                          - a.loc[common, "saidi_without"]),
        }).dropna()
        hur = d["state"].isin(HURRICANE_2017_STATES)

        def cw(mask, col):
            sub = d[mask]
            return float(np.average(sub[col], weights=sub["cust"])) if len(sub) else np.nan

        top = (d.assign(c=(d["d_excluded"] * d["cust"]).abs())
                 .groupby("state")["c"].sum().idxmax())
        rows[f"{first}_{last}"] = {
            "n_hurricane_states_rows": int(hur.sum()),
            "d_excluded_hurricane_cw": cw(hur, "d_excluded"),
            "d_excluded_other_cw": cw(~hur, "d_excluded"),
            "d_everyday_hurricane_cw": cw(hur, "d_without"),
            "d_everyday_other_cw": cw(~hur, "d_without"),
            "excluded_gap_minutes": cw(hur, "d_excluded") - cw(~hur, "d_excluded"),
            "largest_mover_state": str(top),
        }
    share_customers = float(
        100 * b.loc[b["state"].isin(HURRICANE_2017_STATES), "customers"].sum()
        / b["customers"].sum())
    gaps = {k: v["excluded_gap_minutes"] for k, v in rows.items()}
    peak = max(gaps, key=lambda k: gaps[k])
    return {
        "hurricane_states": list(HURRICANE_2017_STATES),
        "hurricane_states_share_of_panel_customers_pct": share_customers,
        "by_transition": rows,
        "largest_excluded_gap_transition": peak,
        "largest_excluded_gap_minutes": float(gaps[peak]),
        "second_largest_excluded_gap_minutes": float(
            sorted(gaps.values(), reverse=True)[1]),
        "reading": ("the hurricane-state list is fixed from the 2017 storm "
                    "tracks and applied to every transition, so 2017 has to "
                    "distinguish itself rather than being selected"),
    }


def _fig(df: pd.DataFrame, tt: dict, step: dict) -> None:
    import matplotlib.pyplot as plt
    yrs = sorted(tt["by_year"])
    w = [tt["by_year"][y]["saidi_with_cw"] for y in yrs]
    wo = [tt["by_year"][y]["saidi_without_cw"] for y in yrs]

    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    ax.plot(yrs, w, marker="o", color=PALETTE["with_med"], lw=2.2,
            label="reported with major event days")
    ax.plot(yrs, wo, marker="o", color=PALETTE["without_med"], lw=2.2,
            label="reported without major event days")
    ax.fill_between(yrs, wo, w, color=PALETTE["accent"], alpha=0.18,
                    label="excluded as major events")
    for a, b in zip(yrs[:-1], yrs[1:]):
        if b - a > 1:
            ax.axvspan(a + 0.1, b - 0.1, color=PALETTE["grid"], alpha=0.55,
                       zorder=0)
            ax.text((a + b) / 2, min(wo) * 0.55, "no filings\nvendored",
                    ha="center", va="bottom", fontsize=7.5,
                    color=PALETTE["muted"], zorder=1)
    ax.set_xticks(yrs)
    ax.set_xlabel("EIA-861 filing year")
    ax.set_ylabel("customer-weighted SAIDI (min/yr)")
    ax.set_title("The everyday line creeps. The excluded portion spikes.",
                 loc="left", fontsize=11)
    ax.text(0.0, 1.015, f"Balanced panel of {tt['by_year'][yrs[0]]['n']} "
            "utility-states present in every filing year",
            transform=ax.transAxes, fontsize=8.5, color=PALETTE["muted"])
    ax.legend(frameon=False, fontsize=8.5)
    style_axes(ax)
    fig.text(0.005, -0.05,
             "The red series trends at 3.21 min/yr (p = 0.006). The gap has no "
             "significant linear trend; it is dominated by 2017.\nNo external "
             "weather index is available, but the geographic placebo in "
             "spike_geography() shows the 2017 rise is\nconcentrated in "
             "hurricane-track states whose everyday series did not move.",
             fontsize=7.5, color=PALETTE["muted"], ha="left", va="top")
    save_figure(fig, "track2_med_gap_trend")


def _fig_placebo(geo: dict) -> None:
    """The geographic placebo, which is the closest thing here to a weather test."""
    import matplotlib.pyplot as plt
    keys = list(geo["by_transition"])
    hur = [geo["by_transition"][k]["d_excluded_hurricane_cw"] for k in keys]
    oth = [geo["by_transition"][k]["d_excluded_other_cw"] for k in keys]
    eve = [geo["by_transition"][k]["d_everyday_hurricane_cw"] for k in keys]
    x = np.arange(len(keys))

    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    ax.bar(x - 0.22, hur, 0.44, color=PALETTE["without_med"],
           label="excluded minutes, hurricane-track states")
    ax.bar(x + 0.22, oth, 0.44, color=PALETTE["muted"],
           label="excluded minutes, everywhere else")
    ax.plot(x, eve, marker="o", ms=5, lw=1.8, color=PALETTE["with_med"],
            label="everyday minutes, hurricane-track states")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([k.replace("_", "\u2013") for k in keys], fontsize=8.5)
    ax.set_ylabel("change in customer-weighted SAIDI (min/yr)")
    ax.set_title("The exclusion spikes where the storms were, then gives it back",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    style_axes(ax)
    fig.text(0.005, -0.05,
             "State list fixed from the 2017 Atlantic hurricane tracks (Harvey, "
             "Irma, Maria, Nate) and applied unchanged to every\ntransition, so "
             "2017 has to distinguish itself rather than be selected. Those "
             f"states hold {geo['hurricane_states_share_of_panel_customers_pct']:.0f}% "
             "of panel customers.",
             fontsize=7.5, color=PALETTE["muted"], ha="left", va="top")
    save_figure(fig, "track2_hurricane_placebo")


def run(save: bool = True) -> dict:
    df = balanced_panel(ALL_YEARS)
    tt = trend_table(df)
    out = {
        "blocker": ("no external weather severity index: NOAA blocked, no "
                    "mirrored storm panel keyed to service territories found. A "
                    "widening major-event gap cannot be split into weather "
                    "severity versus classification."),
        "balanced_panel_utility_states": int(df["utility_state"].nunique()),
        "trend": tt,
        "gradual_or_step": gradual_or_step(df),
        "within_utility": within_utility_decomposition(df, 2013, 2022),
        "within_utility_consecutive": within_utility_decomposition(
            balanced_panel(CONSECUTIVE), 2013, 2018),
        "exclusion_entry": exclusion_entry(df),
        "spike_geography": spike_geography(df),
    }
    if save:
        _fig(df, tt, out["gradual_or_step"])
        _fig_placebo(out["spike_geography"])
        save_results("track2_weather_split", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
