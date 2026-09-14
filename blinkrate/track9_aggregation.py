"""Track 9 - how much of the national number is the averaging rule?

THE QUESTION. Q1 showed that the exclusion threshold moves reported utility
SAIDI. But "US reliability" is not a utility number, it is an aggregate, and
aggregating requires a second choice nobody states: what to average over.
Attack A7 forced this question by showing that the customer-weighted national
figure is dominated by a handful of enormous storm-exposed utilities. This track
asks what the aggregation rule alone is worth.

WHY IT IS NOT A TECHNICALITY. The candidate aggregators answer genuinely
different questions, and all of them are defensible:

  customer-weighted mean   total societal outage burden per customer
  unweighted mean          the average utility's performance
  median utility           the typical utility
  customer-weighted median what the median CUSTOMER experienced
  trimmed / winsorized     the central tendency with catastrophe removed

The customer-weighted mean is the one in general use, and it is the most
exposed to the tail. In 2022 a single Florida co-operative reported over nine
days of outage per customer after Hurricane Ian, and the ten largest
contributors account for a large share of the national total.

WHAT THIS TRACK ADDS TO Q1. The two measurement choices compound. A national
SAIDI figure requires picking a threshold AND picking an aggregator, and neither
is written down in most places the number appears. `combined_space()` reports the
full range of defensible values.

WHAT IT CHECKS ON Q4. Q4 claims the everyday deterioration trend is national and
robust. That claim was tested against dropping states; it has not been tested
against changing the aggregator. If the trend only exists under customer
weighting, Q4 is weaker than it says. `trend_by_aggregator()` settles it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .shared import finite_sample as fs
from .shared import ingest
from .shared import reliability_metrics as rm
from .shared.io import PALETTE, save_figure, save_results, style_axes

TRIM = 0.01
BETAS = np.array([1.5, 2.0, 2.5, 3.0])


def _weighted_quantile(values: np.ndarray, weights: np.ndarray,
                       q: float = 0.5) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(cum, q)])


def aggregators(values: np.ndarray, weights: np.ndarray) -> dict:
    """Every defensible way to turn utility filings into one national number."""
    lo, hi = np.quantile(values, TRIM), np.quantile(values, 1 - TRIM)
    keep = (values >= lo) & (values <= hi)
    wins = np.clip(values, lo, hi)
    return {
        "customer_weighted_mean": float(np.average(values, weights=weights)),
        "unweighted_mean": float(values.mean()),
        "median_utility": float(np.median(values)),
        "customer_weighted_median": _weighted_quantile(values, weights),
        "trimmed_customer_weighted_mean": float(
            np.average(values[keep], weights=weights[keep])),
        "winsorized_customer_weighted_mean": float(
            np.average(wins, weights=weights)),
    }


def by_year(df: pd.DataFrame) -> dict:
    out = {}
    for year, sub in df.groupby("year"):
        w = sub["customers"].to_numpy()
        row = {"n": int(len(sub)), "customers": float(w.sum())}
        for series, tag in (("saidi_without", "without_med"),
                            ("saidi_with", "with_med")):
            agg = aggregators(sub[series].to_numpy(), w)
            row[tag] = agg
            row[f"{tag}_spread_x"] = float(max(agg.values()) / min(agg.values()))
        out[int(year)] = row
    return out


def concentration(df: pd.DataFrame) -> dict:
    """How much of the national total do a handful of filings supply?

    Customer-outage-minutes, which is what a customer-weighted mean is really
    summing. If this is concentrated, the national mean is a statement about a
    few utilities however many file.
    """
    out = {}
    for year, sub in df.groupby("year"):
        row = {}
        for series, tag in (("saidi_without", "without_med"),
                            ("saidi_with", "with_med")):
            total = (sub[series] * sub["customers"]).to_numpy()
            ordered = np.sort(total)[::-1]
            share = ordered.cumsum() / ordered.sum()
            row[tag] = {
                f"top_{k}_share": float(share[k - 1])
                for k in (1, 5, 10, 25) if k <= len(ordered)
            }
            row[f"{tag}_gini"] = _gini(total)
        out[int(year)] = row
    return out


def _gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def combined_space(df: pd.DataFrame, year: int = 2022) -> dict:
    """Threshold choice and aggregation choice together.

    For each beta, re-derive what every utility would have filed (Q1's
    model-implied counterfactual), then aggregate it every way. The result is the
    space of numbers someone could publish as "national SAIDI" while making only
    defensible choices.
    """
    sub = df[df["year"] == year]
    r = sub["retained_share"].to_numpy()
    saidi_with = sub["saidi_with"].to_numpy()
    w = sub["customers"].to_numpy()
    curve = fs.sensitivity_curve_fs(r, BETAS)
    ok = np.isfinite(curve).all(axis=1)

    grid = {}
    for k, b in enumerate(BETAS):
        vals = saidi_with[ok] * curve[ok, k]
        grid[f"beta_{b}"] = aggregators(vals, w[ok])

    flat = [v for row in grid.values() for v in row.values()]
    return {
        "year": year,
        "n_admissible": int(ok.sum()),
        "grid": grid,
        "min": float(min(flat)), "max": float(max(flat)),
        "range_x": float(max(flat) / min(flat)),
        "standard_choice": grid["beta_2.5"]["customer_weighted_mean"],
        "note": ("restricted to utility-years the exclusion model can represent, "
                 "so these are not directly comparable to the filed aggregates "
                 "in by_year()"),
    }


def trend_by_aggregator(df: pd.DataFrame,
                        years=(2013, 2014, 2015, 2016, 2017, 2018)) -> dict:
    """Does Q4's everyday deterioration trend survive the aggregation choice?

    Q4 was tested against dropping states and held. It has not been tested
    against changing the averaging rule, and a trend that only exists under one
    weighting is not the national fact Q4 claims.

    Computed on utilities balanced across the consecutive window, so entry and
    exit cannot generate a trend.
    """
    d = df[df["year"].isin(years)]
    n = d.groupby("utility_state")["year"].nunique()
    b = d[d["utility_state"].isin(n[n == len(years)].index)]

    series = {}
    for year, sub in b.groupby("year"):
        series[int(year)] = aggregators(sub["saidi_without"].to_numpy(),
                                        sub["customers"].to_numpy())

    yrs = np.array(sorted(series))
    out = {"years": list(years), "n_utility_states": int(b["utility_state"].nunique())}
    fits = {}
    for name in series[yrs[0]]:
        vals = np.array([series[y][name] for y in yrs])
        f = stats.linregress(yrs, vals)
        fits[name] = {"slope_min_per_year": float(f.slope),
                      "p": float(f.pvalue), "r2": float(f.rvalue ** 2)}
    out["fits"] = fits
    out["all_positive"] = bool(all(v["slope_min_per_year"] > 0 for v in fits.values()))
    out["all_significant_at_05"] = bool(all(v["p"] < 0.05 for v in fits.values()))
    out["slope_range"] = [float(min(v["slope_min_per_year"] for v in fits.values())),
                          float(max(v["slope_min_per_year"] for v in fits.values()))]
    out["verdict"] = ("Q4's trend is aggregator-robust if every rule gives a "
                      "positive, significant slope")
    return out


def _fig(df: pd.DataFrame, yb: dict, cs: dict) -> None:
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.4))

    year = max(yb)
    names = ["customer_weighted_mean", "unweighted_mean",
             "trimmed_customer_weighted_mean", "customer_weighted_median",
             "median_utility"]
    labels = ["customer-weighted\nmean", "unweighted\nmean", "trimmed\ncw mean",
              "customer-weighted\nmedian", "median\nutility"]
    xs = np.arange(len(names))
    ax1.bar(xs - 0.2, [yb[year]["with_med"][n] for n in names], 0.4,
            color=PALETTE["with_med"], label="with major event days")
    ax1.bar(xs + 0.2, [yb[year]["without_med"][n] for n in names], 0.4,
            color=PALETTE["without_med"], label="without major event days")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(labels, fontsize=7.5)
    ax1.set_ylabel("national SAIDI (min/yr)")
    ax1.set_title(f"Five defensible ways to average {year}", loc="left",
                  fontsize=10.5)
    ax1.legend(frameon=False, fontsize=8)
    style_axes(ax1)

    yrs = sorted(yb)
    for a, b in zip(yrs[:-1], yrs[1:]):
        if b - a > 1:
            ax2.axvspan(a + 0.1, b - 0.1, color=PALETTE["grid"], alpha=0.55,
                        zorder=0)
    for name, color, ls in (("customer_weighted_mean", PALETTE["with_med"], "-"),
                            ("unweighted_mean", PALETTE["accent"], "-"),
                            ("median_utility", PALETTE["without_med"], "--"),
                            ("customer_weighted_median", PALETTE["muted"], "--")):
        ax2.plot(yrs, [yb[y]["without_med"][name] for y in yrs], marker="o",
                 ms=4, lw=1.9, color=color, ls=ls,
                 label=name.replace("_", " "))
    ax2.set_xticks(sorted(yb))
    ax2.set_xlabel("EIA-861 filing year")
    ax2.set_ylabel("national SAIDI without MED (min/yr)")
    # Not "the slope does not depend on the rule". trend_by_aggregator() shows
    # only four of six slopes reach p < 0.05 and they span 1.64 to 4.61 min/yr.
    # The direction is unanimous; the rate is not.
    ax2.set_title("Every rule slopes up. How steeply is another matter.",
                  loc="left", fontsize=10.5)
    ax2.legend(frameon=False, fontsize=7.5)
    style_axes(ax2)
    fig.tight_layout()
    fig.text(0.005, -0.03,
             "All six aggregators give a positive slope over 2013-2018; four of "
             "six reach p < 0.05, and the slopes span 1.64 to 4.61 min/yr. "
             "Shaded band marks filing years not vendored.",
             fontsize=7.5, color=PALETTE["muted"], ha="left", va="top")
    save_figure(fig, "track9_aggregation")


def run(save: bool = True) -> dict:
    df = ingest.analysis_sample()
    yb = by_year(df)
    out = {
        "by_year": yb,
        "concentration": concentration(df),
        "combined_space": combined_space(df),
        "trend_by_aggregator": trend_by_aggregator(df),
        "latest_year_spread": {
            "year": max(yb),
            "with_med_spread_x": yb[max(yb)]["with_med_spread_x"],
            "without_med_spread_x": yb[max(yb)]["without_med_spread_x"],
        },
    }
    if save:
        _fig(df, yb, out["combined_space"])
        save_results("track9_aggregation", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
