"""Track 1 - does capital deployment show up in reported reliability?

THE QUESTION. Utilities spend billions on distribution capital and report
reliability metrics to the federal government. Does the second respond to the
first?

THE SUBSTITUTION, STATED UP FRONT. The question as scoped wanted FERC Form 1
capex per customer. ferc.gov is unreachable and no mirrored Form 1 dataset
exists on GitHub, so there is no spending variable anywhere in this repository.
What EIA-861 does publish is physical capital DEPLOYMENT: how many meters a
utility has converted to AMI, and how many distribution circuits carry voltage
optimisation. Those are outputs of capital programmes. Nothing here speaks to
cost-effectiveness, only to whether deployment and reported reliability move
together.

THE IDENTIFICATION PROBLEM, AND WHY THE ANSWER DEPENDS ON IT. An earlier version
of this track ran a 2022 cross-section, found nothing, and reported a null. That
null was an artefact of when it was measured. By 2022 AMI is nearly universal:
the interquartile range of AMI share is 0.96 to 1.00 and roughly half of
utility-states sit at exactly 1.00. A regressor with no spread cannot detect
anything.

Adding the 2016-2018 filings fixes it. In 2016 the interquartile range of AMI
share is 0.04 to 1.00, and 589 utility-states are observed in all three years
with 53 of them moving AMI share by more than 0.5 inside that window. That is a
rollout observed within the same utility, which supports a within-utility design
rather than a cross-sectional one.

So this track reports three estimates of the same object in ascending order of
credibility, and the point is how much the answer moves:

  (1) cross-section, one year at a time - confounded by everything
  (2) utility fixed effects, 2016-2018 - identified off within-utility change
  (3) long difference, 2016 to 2018 - the same thing, transparently

plus a variance decomposition that caps how much any of them could explain.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .shared import ingest
from .shared.io import PALETTE, save_figure, save_results, style_axes

PANEL_YEARS = (2016, 2017, 2018)
MDE_MULTIPLIER = 2.8  # two-sided 5% test, 80% power


def _cluster_ols(y, X, groups, report):
    X = sm.add_constant(X.astype(float), has_constant="add")
    m = sm.OLS(y.astype(float), X).fit(cov_type="cluster",
                                       cov_kwds={"groups": groups})
    out = {"n": int(m.nobs), "r2": float(m.rsquared),
           "n_clusters": int(pd.Series(groups).nunique()), "coefficients": {}}
    for r in report:
        if r not in m.params:
            continue
        ci = m.conf_int().loc[r]
        out["coefficients"][r] = {
            "beta": float(m.params[r]), "se": float(m.bse[r]),
            "p": float(m.pvalues[r]),
            "ci95": [float(ci[0]), float(ci[1])],
            "mde_80pct_power": float(MDE_MULTIPLIER * m.bse[r]),
            "mde_as_pct_saidi": float(
                100 * (np.exp(-MDE_MULTIPLIER * m.bse[r]) - 1)),
        }
    return out


def cross_sections(df):
    """(1) One year at a time. Reported so the reader can watch it degrade."""
    out = {}
    for year in ingest.DEPLOYMENT_YEARS:
        d = df[df["year"] == year].dropna(
            subset=["log_saidi_without", "ami_share", "log_customers"]).copy()
        if len(d) < 50:
            continue
        X = d[["ami_share", "log_customers"]].copy()
        keep = d["state"].value_counts()
        st = d["state"].where(d["state"].isin(keep[keep >= 5].index), "OTHER")
        X = pd.concat([X,
                       pd.get_dummies(st, prefix="st", drop_first=True,
                                      dtype=float),
                       pd.get_dummies(d["ownership_class"], prefix="own",
                                      drop_first=True, dtype=float)], axis=1)
        res = _cluster_ols(d["log_saidi_without"], X, d["state"], ["ami_share"])
        res["ami_share_iqr"] = [float(d["ami_share"].quantile(0.25)),
                                float(d["ami_share"].quantile(0.75))]
        res["ami_share_sd"] = float(d["ami_share"].std())
        res["share_at_100pct"] = float((d["ami_share"] >= 0.999).mean())
        out[str(year)] = res
    return out


def balanced_panel(df):
    d = df[df["year"].isin(PANEL_YEARS)].dropna(
        subset=["log_saidi_without", "ami_share"]).copy()
    n = d.groupby("utility_state")["year"].nunique()
    return d[d["utility_state"].isin(n[n == len(PANEL_YEARS)].index)].copy()


def within_utility(df):
    """(2) Utility fixed effects, 2016-2018.

    Demeaned by hand rather than by adding 589 dummy columns: identical
    coefficients, and it keeps the design matrix readable. Year dummies stay in
    levels so a common shock (a bad storm year) is absorbed. Standard errors
    clustered on utility-state, the same unit the within transformation uses.
    """
    b = balanced_panel(df)
    if b.empty:
        return {"n": 0}

    def demean(col):
        return b[col] - b.groupby("utility_state")[col].transform("mean")

    y = demean("log_saidi_without")
    X = pd.DataFrame({"ami_share": demean("ami_share")}, index=b.index)
    report = ["ami_share"]
    if b["volt_opt_share"].notna().mean() > 0.5:
        X["volt_opt_share"] = demean("volt_opt_share").fillna(0.0)
        report.append("volt_opt_share")
    X = pd.concat([X, pd.get_dummies(b["year"], prefix="yr", drop_first=True,
                                     dtype=float)], axis=1)

    res = _cluster_ols(y, X, b["utility_state"], report)
    moves = b.groupby("utility_state")["ami_share"].agg(["min", "max"])
    res.update({
        "years": list(PANEL_YEARS),
        "n_utility_states": int(b["utility_state"].nunique()),
        "n_moving_ami_gt_0_10": int(((moves["max"] - moves["min"]) > 0.10).sum()),
        "n_moving_ami_gt_0_50": int(((moves["max"] - moves["min"]) > 0.50).sum()),
        "mean_within_utility_sd_ami": float(
            b.groupby("utility_state")["ami_share"].std().mean()),
        "note": "coefficients are within-utility; year effects absorbed",
    })
    return res


def long_difference(df):
    """(3) 2016 to 2018, in changes. Same identification, easier to check.

    Also splits the sample bluntly: utilities that rolled AMI out during the
    window against those that did not move, comparing their change in log SAIDI
    directly. If the regression coefficient is real, the rollout group should
    improve relative to the stable group.
    """
    b = balanced_panel(df)
    a = b[b["year"] == PANEL_YEARS[0]].set_index("utility_state")
    z = b[b["year"] == PANEL_YEARS[-1]].set_index("utility_state")
    common = a.index.intersection(z.index)
    a, z = a.loc[common], z.loc[common]

    d = pd.DataFrame({
        "d_log_saidi": z["log_saidi_without"] - a["log_saidi_without"],
        "d_ami": z["ami_share"] - a["ami_share"],
        "log_customers": a["log_customers"],
        "state": a["state"],
    }).dropna()

    counts = d["state"].value_counts()
    st = d["state"].where(d["state"].isin(counts[counts >= 5].index), "OTHER")
    X = pd.concat([d[["d_ami", "log_customers"]],
                   pd.get_dummies(st, prefix="st", drop_first=True,
                                  dtype=float)], axis=1)
    res = _cluster_ols(d["d_log_saidi"], X, d["state"], ["d_ami"])

    rollout = d["d_ami"] > 0.5
    stable = d["d_ami"].abs() < 0.05
    diff = (d.loc[rollout, "d_log_saidi"].mean()
            - d.loc[stable, "d_log_saidi"].mean())
    res["group_comparison"] = {
        "n_rollout": int(rollout.sum()), "n_stable": int(stable.sum()),
        "mean_d_log_saidi_rollout": float(d.loc[rollout, "d_log_saidi"].mean()),
        "mean_d_log_saidi_stable": float(d.loc[stable, "d_log_saidi"].mean()),
        "difference": float(diff),
        "pct_saidi_difference": float(100 * (np.exp(diff) - 1)),
    }
    res["span"] = f"{PANEL_YEARS[0]} to {PANEL_YEARS[-1]}"
    return res


def variance_decomposition(years=(2013, 2014, 2015, 2016, 2017, 2018)):
    """What ceiling does persistence put on any utility-level regressor?

    Six consecutive years now rather than three. A cross-sectional regressor can
    only reach the between-utility share; the within share is year-to-year shock
    that no time-invariant characteristic explains.
    """
    df = ingest.analysis_sample()
    df = df[df["year"].isin(years)].copy()
    df["log_saidi"] = np.log(df["saidi_without"].where(df["saidi_without"] > 0))
    df["log_saidi_with_med"] = np.log(df["saidi_with"].where(df["saidi_with"] > 0))
    df = df.dropna(subset=["log_saidi", "log_saidi_with_med"])
    counts = df.groupby("utility_state")["year"].nunique()
    b = df[df["utility_state"].isin(counts[counts == len(years)].index)]

    def split(col):
        means = b.groupby("utility_state")[col].transform("mean")
        between = ((means - b[col].mean()) ** 2).sum()
        within = ((b[col] - means) ** 2).sum()
        return between / (between + within), within / (between + within)

    bw, wi = split("log_saidi")
    bw2, _ = split("log_saidi_with_med")
    return {
        "years": list(years),
        "n_utility_states_balanced": int(b["utility_state"].nunique()),
        "n_rows": int(len(b)),
        "share_between_utility": float(bw),
        "share_within_utility": float(wi),
        "share_between_utility_with_med": float(bw2),
        "reading": ("the between share is the ceiling for any time-invariant "
                    "utility characteristic; the with-MED series is far less "
                    "persistent because major events are a year-specific shock"),
    }


def _fig(df, cs):
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.8, 4.2))

    yrs = sorted(int(y) for y in cs)
    lo = [cs[str(y)]["ami_share_iqr"][0] for y in yrs]
    hi = [cs[str(y)]["ami_share_iqr"][1] for y in yrs]
    ax1.fill_between(yrs, lo, hi, color=PALETTE["with_med"], alpha=0.25,
                     label="interquartile range of AMI share")
    ax1.plot(yrs, lo, color=PALETTE["with_med"], lw=2)
    ax1.plot(yrs, hi, color=PALETTE["with_med"], lw=2)
    ax1.plot(yrs, [cs[str(y)]["share_at_100pct"] for y in yrs], ls="--", lw=2,
             marker="o", ms=4, color=PALETTE["without_med"],
             label="share already at 100%")
    ax1.set_xticks(yrs)
    ax1.set_ylim(0, 1.02)
    ax1.set_xlabel("EIA-861 filing year")
    ax1.set_ylabel("AMI share of customers")
    ax1.set_title("The regressor runs out of variation", loc="left", fontsize=10.5)
    ax1.legend(frameon=False, fontsize=8, loc="lower left")
    style_axes(ax1)

    b = balanced_panel(df)
    a = b[b["year"] == PANEL_YEARS[0]].set_index("utility_state")
    z = b[b["year"] == PANEL_YEARS[-1]].set_index("utility_state")
    common = a.index.intersection(z.index)
    d_ami = z.loc[common, "ami_share"] - a.loc[common, "ami_share"]
    d_saidi = (z.loc[common, "log_saidi_without"]
               - a.loc[common, "log_saidi_without"])
    ok = d_ami.notna() & d_saidi.notna()
    ax2.scatter(d_ami[ok], d_saidi[ok], s=16, alpha=0.45,
                color=PALETTE["with_med"], edgecolor="none")
    if ok.sum() > 10:
        co = np.polyfit(d_ami[ok], d_saidi[ok], 1)
        xs = np.linspace(float(d_ami[ok].min()), float(d_ami[ok].max()), 50)
        ax2.plot(xs, np.polyval(co, xs), color=PALETTE["without_med"], lw=2)
    ax2.axhline(0, color=PALETTE["muted"], lw=0.8)
    ax2.set_xlabel(f"change in AMI share, {PANEL_YEARS[0]} to {PANEL_YEARS[-1]}")
    ax2.set_ylabel("change in log SAIDI without MED")
    ax2.set_title("Within utility, the rollout leaves no trace", loc="left",
                  fontsize=10.5)
    style_axes(ax2)
    fig.tight_layout()
    save_figure(fig, "track1_ami_identification")


def run(save=True):
    df = ingest.deployment_panel()
    cs = cross_sections(df)
    out = {
        "substitution": (
            "FERC Form 1 capex unreachable; regressors are physical capital "
            "deployment (AMI share, voltage-optimised circuit share) from "
            "EIA-861, not spending"
        ),
        "cross_sections": cs,
        "within_utility": within_utility(df),
        "long_difference": long_difference(df),
        "variance_decomposition": variance_decomposition(),
    }
    if save:
        _fig(df, cs)
        save_results("track1_investment", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
