"""Track 3 (headline) - how much of a reported SAIDI is the threshold parameter?

QUESTION AS SPECIFIED: how much does a utility's reported SAIDI change if the
2.5-beta exclusion threshold is tightened or loosened, and do utilities cluster
near a threshold that flatters their numbers?

WHAT CHANGED, AND WHY. The first half is answered here as specified, by a route
the spec did not anticipate. The second half is not, and the reason is a data
fact worth stating up front rather than burying: EIA-861 publishes annual SAIDI
with and without major event days, not the daily SAIDI series. The 2.5-beta
threshold is computed from a utility's own five-year daily history, so it cannot
be recomputed from what is published. Nothing in this repo sweeps beta on
observed daily data, because no such data is public at national scale.

What makes the sweep possible anyway is that the exclusion has a closed form.
If daily SAIDI is log-normal - the distribution IEEE 1366 itself assumes - the
share of annual outage minutes surviving exclusion is Phi(beta - sigma), which
depends only on the dispersion of daily SAIDI. Two published numbers therefore
pin the one latent parameter, and the sweep runs on that. It is a model-implied
sensitivity that inherits 1366's own assumption; track 8 attacks the assumption.

The bunching test also changed, and not into something weaker. Beta is not a
utility's choice - it is written into the standard - so there is no kink for a
utility to bunch at, and testing for one would be testing a hypothesis the
institutional setup rules out. The discretion that does exist in this data is
discrete: whether to claim any major event days at all, and whether to report
under IEEE 1366 or under a self-defined "Other" standard. Both are observable,
and the first produces a genuine mass point that a real excess-mass estimator
can measure. That is what is tested below.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .shared import finite_sample as fs
from .shared import ingest
from .shared import reliability_metrics as rm
from .shared.io import PALETTE, save_figure, save_results, style_axes

BETA_SWEEP = np.round(np.arange(1.5, 3.51, 0.05), 3)
BETA_HEADLINE = np.array([1.5, 2.0, 2.5, 3.0, 3.5])


def model_coverage(df: pd.DataFrame) -> dict:
    """How much of what utilities report can IEEE 1366's own model produce?"""
    cal = fs.calibration()
    j = int(np.argmin(np.abs(cal["beta_grid"] - rm.BETA_STANDARD)))
    r_max = float(cal["surface"][0, j])   # sigma at the bottom of the grid
    r_min = float(cal["surface"][-1, j])  # sigma at the top of the grid
    r = df["retained_share"].to_numpy()
    sigma = fs.implied_sigma_fs(r)
    return {
        "n": int(len(df)),
        "r_max_modelable": r_max,
        "r_min_modelable": r_min,
        "n_too_clean": int((r > r_max).sum()),
        "share_too_clean": float((r > r_max).mean()),
        "n_exactly_zero_exclusion": int((r >= 1 - 1e-9).sum()),
        "share_exactly_zero_exclusion": float((r >= 1 - 1e-9).mean()),
        "n_too_excluded": int((r < r_min).sum()),
        "share_too_excluded": float((r < r_min).mean()),
        "n_admissible": int(np.isfinite(sigma).sum()),
        "share_admissible": float(np.isfinite(sigma).mean()),
        "implied_sigma_quantiles": {
            str(q): float(np.nanpercentile(sigma, q)) for q in (10, 25, 50, 75, 90)
        },
    }


def sensitivity(df: pd.DataFrame) -> dict:
    """Fleet-level reported SAIDI as a function of the threshold parameter.

    Restricted to utility-years the model can represent. The 31% that report
    less exclusion than any non-negative sigma produces are reported separately
    rather than clipped in, because clipping them to sigma = 0 would silently
    assert they have perfectly uniform daily outage minutes.
    """
    r = df["retained_share"].to_numpy()
    saidi_with = df["saidi_with"].to_numpy()
    curve = fs.sensitivity_curve_fs(r, BETA_SWEEP)
    ok = np.isfinite(curve).all(axis=1)

    fleet = np.array([np.average(saidi_with[ok] * curve[ok, k],
                                 weights=df["customers"].to_numpy()[ok])
                      for k in range(BETA_SWEEP.size)])
    unweighted = (saidi_with[ok][:, None] * curve[ok]).mean(axis=0)
    base_idx = int(np.argmin(np.abs(BETA_SWEEP - rm.BETA_STANDARD)))

    # Expected number of qualifying days per year at each beta: a day exceeds
    # exp(mu + beta*sigma) with probability 1 - Phi(beta), independent of sigma.
    exp_med_days = rm.DAYS_PER_YEAR * (1 - stats.norm.cdf(BETA_SWEEP))

    headline = {}
    for b in BETA_HEADLINE:
        k = int(np.argmin(np.abs(BETA_SWEEP - b)))
        headline[f"beta_{b:.1f}"] = {
            "fleet_saidi_without_med": float(fleet[k]),
            "unweighted_mean_saidi_without_med": float(unweighted[k]),
            "pct_change_vs_2_5": float(100 * (fleet[k] / fleet[base_idx] - 1)),
            "median_retained_share": float(np.median(curve[ok, k])),
            "expected_med_days_per_year": float(exp_med_days[k]),
        }
    return {
        "n_admissible_rows": int(ok.sum()),
        "beta_grid": BETA_SWEEP.tolist(),
        "fleet_saidi_without_med": fleet.tolist(),
        "headline": headline,
        "fleet_range_ratio": float(fleet.max() / fleet.min()),
        "customer_weighted": True,
    }


def elasticity_identity(df: pd.DataFrame) -> dict:
    """dr/dbeta = phi(Phi^-1(r)): sensitivity is a function of r and nothing else.

    Checked numerically against the calibrated surface, since the identity is
    derived from the closed form and the tracks run on the finite-sample map.
    """
    r = df["retained_share"].to_numpy()
    interior = r[(r > 0.02) & (r < 0.98)]
    analytic = rm.d_retained_d_beta(interior)

    h = 0.05
    sig = fs.implied_sigma_fs(interior)
    ok = np.isfinite(sig)
    up = fs.retained_share_fs(sig[ok], rm.BETA_STANDARD + h).ravel()
    dn = fs.retained_share_fs(sig[ok], rm.BETA_STANDARD - h).ravel()
    numeric = (up - dn) / (2 * h)

    return {
        "n": int(ok.sum()),
        "max_analytic_dr_dbeta": float(analytic.max()),
        "analytic_at_r_half": float(rm.d_retained_d_beta(np.array([0.5]))[0]),
        "median_analytic": float(np.median(analytic)),
        "median_numeric_finite_sample": float(np.median(numeric)),
        "corr_analytic_vs_numeric": float(np.corrcoef(analytic[ok], numeric)[0, 1]),
        "note": ("analytic is the closed-form identity, numeric differentiates the "
                 "finite-sample surface; they agree in shape, not in level"),
    }


def _bunching_design(edges: np.ndarray, centers: np.ndarray,
                     in_window: np.ndarray, degree: int):
    """Design matrices for the counterfactual polynomial, outside and inside
    the bunching window.

    A Legendre basis on the fitted points' own range rescaled to [-1, 1], not
    the raw power basis that `np.vander` gives. Both span the same polynomials,
    so the least-squares fit, and therefore the estimator, is identical; the
    window bins are evaluated just outside [-1, 1], which is the extrapolation
    the estimator has always done. What differs is conditioning. Across the
    36-specification grid in attack A3 the power basis reaches a condition
    number of 2.3e8, which left the last few significant digits of every
    bunching result to whichever LAPACK build ran the pseudo-inverse, and under
    numpy 2.5 broke CI's byte-identity check on results that had not changed in
    any reported digit. This basis stays at or below 3.7 across the same grid.

    Scaling to the fitted points rather than to the full bin range matters: the
    full range reaches 352 at degree 7 with the widest window, because the
    fitted points then occupy only part of [-1, 1].
    """
    x_fit = centers[~in_window]
    lo, hi = float(x_fit.min()), float(x_fit.max())

    def basis(x: np.ndarray) -> np.ndarray:
        return np.polynomial.legendre.legvander((2.0 * x - (lo + hi)) / (hi - lo),
                                                degree)

    return basis(x_fit), basis(centers[in_window])


def bunching_design_for(fit_lo: float, window: float, degree: int):
    """The fit-side design matrix for one specification, for conditioning
    checks. Mirrors the binning in `excess_mass_at_zero_exclusion` exactly."""
    edges = np.arange(fit_lo, 1.0 + 1e-9, 0.01)
    centers = (edges[:-1] + edges[1:]) / 2
    in_window = centers > (1 - window)
    return _bunching_design(edges, centers, in_window, degree)


def excess_mass_at_zero_exclusion(df: pd.DataFrame, window: float = 0.05,
                                  degree: int = 5, n_boot: int = 2000,
                                  fit_lo: float = 0.30, seed: int = 7) -> dict:
    """Bunching estimator for the mass at zero exclusion (retained share = 1).

    Chetty-style: fit a flexible polynomial to the density of the retained share
    over [fit_lo, 1 - window], excluding the bunching window, extrapolate the
    counterfactual into the window, and take excess mass as the ratio of observed
    to counterfactual count there.

    Bootstrapped over utility-state clusters, because the same utility appears in
    up to four filing years and treating those as independent would shrink the
    interval for free.

    The bootstrap is vectorised rather than looped. A cluster resample only
    changes how many times each cluster's histogram is added, so the per-cluster
    bin counts are computed once and every draw is a multinomial-weighted matrix
    product; and since the polynomial design matrix is the same for every draw,
    one pseudo-inverse fits all of them at once. Same estimator, three orders of
    magnitude faster, which is what makes the 36-specification robustness grid in
    track 8 affordable. The polynomial is fitted in a well-conditioned basis; see
    `_bunching_design` for why that matters to reproducibility.
    """
    rng = np.random.default_rng(seed)
    r = df["retained_share"].to_numpy()
    clusters = df["utility_state"].to_numpy()

    edges = np.arange(fit_lo, 1.0 + 1e-9, 0.01)
    centers = (edges[:-1] + edges[1:]) / 2
    in_window = centers > (1 - window)
    if in_window.sum() < 2 or (~in_window).sum() <= degree:
        raise ValueError("bunching window or fit range too narrow for this degree")

    uniq, inv = np.unique(clusters, return_inverse=True)
    # (n_clusters, n_bins) histogram, built once
    bin_idx = np.digitize(r, edges) - 1
    valid = (bin_idx >= 0) & (bin_idx < centers.size)
    cluster_hist = np.zeros((uniq.size, centers.size))
    np.add.at(cluster_hist, (inv[valid], bin_idx[valid]), 1.0)

    V_fit, V_win = _bunching_design(edges, centers, in_window, degree)
    pinv = np.linalg.pinv(V_fit)

    def ratios(count_matrix: np.ndarray) -> np.ndarray:
        """count_matrix is (n_draws, n_bins)."""
        coef = pinv @ count_matrix[:, ~in_window].T          # (deg+1, n_draws)
        cf = np.clip(V_win @ coef, 0, None).sum(axis=0)      # (n_draws,)
        obs = count_matrix[:, in_window].sum(axis=1)
        return np.where(cf > 0, obs / np.where(cf > 0, cf, 1), np.nan)

    point = float(ratios(cluster_hist.sum(axis=0)[None, :])[0])

    weights = rng.multinomial(uniq.size, np.full(uniq.size, 1 / uniq.size),
                              size=n_boot).astype(float)
    boot = ratios(weights @ cluster_hist)
    boot = boot[np.isfinite(boot)]

    return {
        "excess_mass_ratio": point,
        "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
        "n_bootstrap_effective": int(boot.size),
        "n_clusters": int(uniq.size),
        "window": window, "poly_degree": degree, "fit_range_lo": fit_lo,
        "observed_count_in_window": int((r > 1 - window).sum()),
    }


def standard_choice(df: pd.DataFrame) -> dict:
    """Does the discretionary choice of reporting standard track the numbers?"""
    g = df.groupby("standard")
    out = {
        s: {
            "n": int(len(sub)),
            "mean_retained_share": float(sub["retained_share"].mean()),
            "median_retained_share": float(sub["retained_share"].median()),
            "share_zero_exclusion": float((sub["retained_share"] >= 1 - 1e-9).mean()),
            "median_saidi_with": float(sub["saidi_with"].median()),
            "median_saidi_without": float(sub["saidi_without"].median()),
        }
        for s, sub in g
    }
    a = df.loc[df["standard"] == "IEEE", "retained_share"]
    b = df.loc[df["standard"] == "Other", "retained_share"]
    u = stats.mannwhitneyu(a, b, alternative="two-sided")
    out["test"] = {
        "mannwhitney_u": float(u.statistic), "p_value": float(u.pvalue),
        "note": ("utility-state-years are not independent across filing years; "
                 "treat the p-value as descriptive, the effect size is the point"),
    }

    switch = (df.groupby("utility_state")["standard"].nunique() > 1)
    out["switchers"] = {
        "n_utility_states": int(switch.size),
        "n_switched_standard": int(switch.sum()),
        "share_switched": float(switch.mean()),
    }
    return out


SIZE_BANDS = ((100, 10_000, "100_to_10k"), (10_000, 100_000, "10k_to_100k"),
              (100_000, float("inf"), "100k_plus"))


def zero_exclusion_benchmark(df: pd.DataFrame) -> dict:
    """How many zero-exclusion filings would genuine segmentation produce?

    EIA's own filing instructions settle what an identical with/without pair
    means: a utility that removes no data reports the same value in both
    columns. So the 29.8% mass point is a reporting practice, and the question
    is how much of it is genuine zero-major-event years versus utilities not
    segmenting at all.

    The standard's design answers the first part. A utility applying the
    2.5-beta method flags each day with probability 1 - Phi(2.5), so it should
    see a year with no qualifying day with probability (1 - p)^365, about
    10.3%. The working group observed two to eight major event days a year on
    donated data rather than 2.3, which moves that to between 0.03% and 13.5%.
    Anything well above 13.5% is more than genuine zero-event years can explain.

    Split by reporting standard and size, because small utilities have lumpy
    daily SAIDI with many zero days, which is exactly where the benchmark
    applies least well (the 2013 IEEE letter on zero-SAIDI days).
    """
    p_day = float(stats.norm.sf(rm.BETA_STANDARD))
    benchmarks = {
        "nominal_2_27_per_year": float((1 - p_day) ** rm.DAYS_PER_YEAR),
        "wg_observed_2_per_year": float(np.exp(-2.0)),
        "wg_observed_8_per_year": float(np.exp(-8.0)),
        "laplace_5_32_per_year": float(np.exp(-rm.DAYS_PER_YEAR * 0.5
                                              * np.exp(-rm.BETA_STANDARD
                                                       * np.sqrt(2.0)))),
    }
    ceiling = max(benchmarks.values())
    zero = df["retained_share"] >= 1 - 1e-9
    table = {}
    for std in ("IEEE", "Other"):
        table[std] = {}
        for lo, hi, label in SIZE_BANDS:
            m = ((df["standard"] == std) & (df["customers"] >= lo)
                 & (df["customers"] < hi))
            table[std][label] = {"n": int(m.sum()),
                                 "share_zero_exclusion": float(zero[m].mean()),
                                 "multiple_of_generous_benchmark": float(
                                     zero[m].mean() / ceiling)}
    large_ieee = table["IEEE"]["100k_plus"]["share_zero_exclusion"]
    return {
        "benchmarks": benchmarks,
        "generous_ceiling": ceiling,
        "by_standard_and_size": table,
        "large_ieee_within_benchmark_range": bool(large_ieee <= ceiling),
        "other_to_ieee_ratio_by_size": {
            label: float(table["Other"][label]["share_zero_exclusion"]
                         / table["IEEE"][label]["share_zero_exclusion"])
            for _, _, label in SIZE_BANDS},
        "source_note": ("EIA-861 FAQ: identical with/without values report that no "
                        "data was removed; benchmark frequencies from Warren et al. "
                        "2003 (IEEE PES GM)"),
    }


def ranking_sensitivity(df: pd.DataFrame, min_customers: int = 100_000,
                        ownership: str = "IOU") -> dict:
    """Does the exclusion change WHO looks reliable, not just by how much?

    Benchmarking is comparative: regulators, trade press and investor decks rank
    utilities against each other. EIA-861 publishes two SAIDI series per utility
    and they are not interchangeable, so the ranking is a choice. This measures
    how much of a choice.

    Restricted to large investor-owned utilities, because that is the population
    that actually gets ranked against itself.
    """
    out = {"min_customers": min_customers, "ownership": ownership, "by_year": {}}
    for year, sub in df[(df["customers"] >= min_customers)
                        & (df["ownership_class"] == ownership)].groupby("year"):
        if len(sub) < 20:
            continue
        n = len(sub)
        rank_with = stats.rankdata(sub["saidi_with"])
        rank_without = stats.rankdata(sub["saidi_without"])
        moves = np.abs(rank_with - rank_without)
        q_with = pd.qcut(sub["saidi_with"], 4, labels=False)
        q_without = pd.qcut(sub["saidi_without"], 4, labels=False)
        out["by_year"][int(year)] = {
            "n": int(n),
            "spearman": float(stats.spearmanr(sub["saidi_with"],
                                              sub["saidi_without"]).statistic),
            "median_rank_move": float(np.median(moves)),
            "median_rank_move_pct_of_field": float(100 * np.median(moves) / n),
            "max_rank_move": float(moves.max()),
            "pct_changing_quartile": float(100 * (q_with != q_without).mean()),
            "pct_entering_or_leaving_best_quartile": float(
                100 * ((q_with == 0) != (q_without == 0)).mean()),
            "excluded_share_p0_p50_p100": [
                float(sub["excluded_share"].quantile(q)) for q in (0, 0.5, 1)],
        }
    yrs = out["by_year"]
    out["pct_changing_quartile_range"] = [
        min(v["pct_changing_quartile"] for v in yrs.values()),
        max(v["pct_changing_quartile"] for v in yrs.values())]
    out["spearman_range"] = [min(v["spearman"] for v in yrs.values()),
                             max(v["spearman"] for v in yrs.values())]

    latest = max(yrs)
    sub = df[(df["year"] == latest) & (df["customers"] >= min_customers)
             & (df["ownership_class"] == ownership)].copy()
    sub["rank_with"] = stats.rankdata(sub["saidi_with"])
    sub["rank_without"] = stats.rankdata(sub["saidi_without"])
    sub["move"] = sub["rank_with"] - sub["rank_without"]
    top = sub.nlargest(5, "move")
    out["largest_gains_latest_year"] = {
        "year": int(latest),
        "n": int(len(sub)),
        "utilities": [
            {"name": r["utility_name"], "state": r["state"],
             "saidi_with": float(r["saidi_with"]),
             "saidi_without": float(r["saidi_without"]),
             "excluded_share": float(r["excluded_share"]),
             "rank_with": int(r["rank_with"]), "rank_without": int(r["rank_without"])}
            for _, r in top.iterrows()],
    }
    out["note"] = ("a large rank gain is not evidence of anything improper. "
                   "Gulf-coast utilities have genuine hurricane days and the "
                   "exclusion exists to remove them. The point is that the two "
                   "series answer different questions, so a benchmark that picks "
                   "one without saying which has made a decision, not a "
                   "measurement")
    return out


def _fig_sensitivity(df: pd.DataFrame, sens: dict) -> None:
    import matplotlib.pyplot as plt
    betas = np.array(sens["beta_grid"])
    fleet = np.array(sens["fleet_saidi_without_med"])
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(betas, fleet, color=PALETTE["with_med"], lw=2.2)
    k = int(np.argmin(np.abs(betas - 2.5)))
    ax.scatter([2.5], [fleet[k]], color=PALETTE["without_med"], zorder=5, s=55)
    ax.annotate(f"IEEE 1366 uses 2.5\n{fleet[k]:.0f} min/yr",
                xy=(2.5, fleet[k]), xytext=(2.62, fleet[k] * 0.62),
                color=PALETTE["without_med"], fontsize=9,
                arrowprops=dict(arrowstyle="->", color=PALETTE["without_med"]))
    ax.set_xlabel("major-event-day threshold parameter  $\\beta$")
    ax.set_ylabel("customer-weighted reported SAIDI\nwithout major event days (min/yr)")
    ax.set_title("The same outage record, reported under a different threshold",
                 loc="left", fontsize=11)
    # The flat top past 2.95 is the exclusion mechanism switching off: with 365
    # days the median year holds no 3-sigma day. Track 8 attack A1 shows that
    # cliff is a property of the log-normal rather than of the rule, so the
    # figure carries the caveat instead of leaving it to the caption.
    fig.text(0.005, -0.06,
             "Model-implied under IEEE 1366's own log-normal assumption for daily "
             "SAIDI. Direction survives heavier tails;\nmagnitude and the flat "
             "region past 2.95 do not (FALSIFICATION.md, attack A1).",
             fontsize=7.5, color=PALETTE["muted"], ha="left", va="top")
    style_axes(ax)
    save_figure(fig, "track3_sensitivity_curve")


def _fig_density(df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt
    r = df["retained_share"].to_numpy()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.hist(r, bins=np.arange(0, 1.0001, 0.01), color=PALETTE["with_med"], alpha=0.85)
    ax.axvline(rm.R_MAX_ADMISSIBLE, color=PALETTE["accent"], ls="--", lw=1.4)
    ax.annotate("$\\Phi(2.5)$: cleanest year the\nlog-normal model can produce",
                xy=(rm.R_MAX_ADMISSIBLE, ax.get_ylim()[1] * 0.55),
                xytext=(0.52, ax.get_ylim()[1] * 0.62), fontsize=9,
                color=PALETTE["accent"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["accent"]))
    n_zero = int((r >= 1 - 1e-9).sum())
    n_all = int((r <= 0.03).sum())
    ax.set_xlabel("retained share  $r$ = SAIDI without MED / SAIDI with MED")
    ax.set_ylabel("utility-state-years")
    ax.set_title("Nearly a third of filings claim no major event days at all",
                 loc="left", fontsize=11)
    fig.text(0.005, -0.06,
             f"{n_zero} filings sit at r = 1 (no exclusion). The smaller spike at "
             f"the left is {n_all} filings reporting that major events\naccount "
             "for essentially all of their outage minutes; both tails are outside "
             "what the log-normal model produces.",
             fontsize=7.5, color=PALETTE["muted"], ha="left", va="top")
    style_axes(ax)
    save_figure(fig, "track3_retained_share_density")


def run(save: bool = True) -> dict:
    df = ingest.analysis_sample()
    out = {
        "coverage": model_coverage(df),
        "sensitivity": sensitivity(df),
        "elasticity": elasticity_identity(df),
        "bunching": excess_mass_at_zero_exclusion(df),
        "standard_choice": standard_choice(df),
        "ranking": ranking_sensitivity(df),
        "zero_exclusion_benchmark": zero_exclusion_benchmark(df),
    }
    if save:
        _fig_sensitivity(df, out["sensitivity"])
        _fig_density(df)
        save_results("track3_med_sensitivity", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
