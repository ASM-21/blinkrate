"""Track 6 - does ownership structure change the exclusion result?

Investor-owned utilities defend reported reliability metrics in rate cases.
Municipals and cooperatives mostly do not face the same scrutiny on the same
numbers. If track 3's exclusion patterns are about regulatory incentives, they
should be sharpest among IOUs. If they are about measurement capability - having
an outage management system that can classify days at all - they should track
utility size instead, and ownership will mostly be a proxy for that.

This track cannot tell those apart cleanly, and says so. IOUs are much larger
than co-ops, so ownership and size are collinear by construction in this data.
What it can do is report the ownership gap before and after conditioning on
size, and report where the gap survives.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .shared import finite_sample as fs
from .shared import ingest
from .shared.io import PALETTE, save_figure, save_results, style_axes

CLASSES = ("IOU", "Coop", "Municipal")


def by_ownership(df: pd.DataFrame) -> dict:
    out = {}
    for cls, sub in df.groupby("ownership_class"):
        if cls not in CLASSES:
            continue
        sigma = fs.implied_sigma_fs(sub["retained_share"].to_numpy())
        out[cls] = {
            "n": int(len(sub)),
            "median_customers": float(sub["customers"].median()),
            "mean_retained_share": float(sub["retained_share"].mean()),
            "median_retained_share": float(sub["retained_share"].median()),
            "share_zero_exclusion": float((sub["retained_share"] >= 1 - 1e-9).mean()),
            "median_saidi_with": float(sub["saidi_with"].median()),
            "median_saidi_without": float(sub["saidi_without"].median()),
            "median_implied_sigma": float(np.nanmedian(sigma)),
            "share_reporting_ieee": float((sub["standard"] == "IEEE").mean()),
        }
    return out


def gap_conditional_on_size(df: pd.DataFrame) -> dict:
    """Is the ownership gap in exclusion still there once size is controlled?

    Linear probability model for zero exclusion and a linear model for the
    retained share, both with log customers, year fixed effects and state fixed
    effects. Coops are the reference class.
    """
    d = df[df["ownership_class"].isin(CLASSES)].dropna(
        subset=["retained_share", "log_customers"]).copy()
    d["zero_exclusion"] = (d["retained_share"] >= 1 - 1e-9).astype(float)

    def fit(y: str, with_size: bool) -> dict:
        X = pd.get_dummies(d["ownership_class"], drop_first=False, dtype=float)
        X = X.drop(columns=["Coop"])
        if with_size:
            X["log_customers"] = d["log_customers"].astype(float)
        X = pd.concat([X, pd.get_dummies(d["year"].astype(int), prefix="yr",
                                         drop_first=True, dtype=float)], axis=1)
        keep = d["state"].value_counts()
        st = d["state"].where(d["state"].isin(keep[keep >= 10].index), "OTHER")
        X = pd.concat([X, pd.get_dummies(st, prefix="st", drop_first=True,
                                         dtype=float)], axis=1)
        X = sm.add_constant(X, has_constant="add")
        m = sm.OLS(d[y].astype(float), X).fit(
            cov_type="cluster", cov_kwds={"groups": d["utility_state"]})
        return {
            "n": int(m.nobs), "r2": float(m.rsquared),
            "IOU_vs_Coop": float(m.params["IOU"]), "IOU_se": float(m.bse["IOU"]),
            "IOU_p": float(m.pvalues["IOU"]),
            "Municipal_vs_Coop": float(m.params["Municipal"]),
            "Municipal_se": float(m.bse["Municipal"]),
            "Municipal_p": float(m.pvalues["Municipal"]),
            "log_customers": float(m.params["log_customers"]) if with_size else None,
            "log_customers_p": float(m.pvalues["log_customers"]) if with_size else None,
        }

    return {
        "retained_share_no_size": fit("retained_share", False),
        "retained_share_with_size": fit("retained_share", True),
        "zero_exclusion_no_size": fit("zero_exclusion", False),
        "zero_exclusion_with_size": fit("zero_exclusion", True),
        "note": ("reference class is Coop; state and year fixed effects in every "
                 "specification; standard errors clustered by utility-state"),
    }


def size_decile_check(df: pd.DataFrame) -> dict:
    """The same comparison inside size deciles, which is the honest version.

    If the IOU gap is really about scrutiny it should survive within a decile.
    If it is about measurement capability it should collapse.
    """
    d = df[df["ownership_class"].isin(CLASSES)].copy()
    d["decile"] = pd.qcut(d["customers"], 10, labels=False, duplicates="drop")
    rows = {}
    for dec, sub in d.groupby("decile"):
        g = sub.groupby("ownership_class")["retained_share"]
        counts = g.count()
        if not {"IOU", "Coop"}.issubset(set(counts[counts >= 15].index)):
            continue
        rows[int(dec)] = {
            "n": int(len(sub)),
            "median_customers": float(sub["customers"].median()),
            "IOU_median_r": float(g.median()["IOU"]),
            "Coop_median_r": float(g.median()["Coop"]),
            "gap_IOU_minus_Coop": float(g.median()["IOU"] - g.median()["Coop"]),
        }
    gaps = [v["gap_IOU_minus_Coop"] for v in rows.values()]
    return {
        "deciles_with_both": len(rows),
        "deciles": rows,
        "n_deciles_iou_excludes_more": int(sum(g < 0 for g in gaps)),
        "median_gap": float(np.median(gaps)) if gaps else np.nan,
    }


def _fig(df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt
    d = df[df["ownership_class"].isin(CLASSES)]
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    colors = {"IOU": PALETTE["without_med"], "Coop": PALETTE["with_med"],
              "Municipal": PALETTE["accent"]}
    for cls in CLASSES:
        v = np.sort(d.loc[d["ownership_class"] == cls, "retained_share"].to_numpy())
        ax.plot(v, np.linspace(0, 1, v.size), lw=2.2, color=colors[cls],
                label=f"{cls} (n={v.size})")
    ax.set_xlabel("retained share  $r$ = SAIDI without MED / SAIDI with MED")
    ax.set_ylabel("cumulative share of utility-state-years")
    ax.set_title("Investor-owned utilities exclude the most", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    style_axes(ax)
    save_figure(fig, "track6_ownership_cdf")


def run(save: bool = True) -> dict:
    df = ingest.analysis_sample()
    out = {
        "by_ownership": by_ownership(df),
        "conditional": gap_conditional_on_size(df),
        "size_deciles": size_decile_check(df),
    }
    if save:
        _fig(df)
        save_results("track6_ownership", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
