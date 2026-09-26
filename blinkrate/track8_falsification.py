"""Track 8 - try to break the other tracks.

Six attacks, aimed at the load-bearing assumptions rather than at the edges.
Results are written to FALSIFICATION.md by tools/write_falsification.py; this
module only computes them. An attack that fails to break a result is recorded
just as carefully as one that succeeds.

A1  Track 3's log-normal assumption. Everything in track 3 rides on IEEE 1366's
    own claim that daily SAIDI is log-normal. Rebuild the calibration under a
    heavier-tailed daily distribution and see whether the sensitivity range
    survives.
A2  Track 3's median statistic. The calibration inverts the median realized
    retained share. Redo it on the mean.
A3  Track 3's bunching estimator. Vary polynomial degree, window width and fit
    range; a bunching result that only exists at one specification is not one.
A4  Track 2's headline. Recompute the share of the SAIDI increase coming from
    the excluded part with the top and bottom 1% of utility-years trimmed.
A5  Track 6's ownership gap. IOUs are far larger than co-ops. Restrict to
    utilities above the median size and see whether the gap survives.
A6  Track 1's null. A null can be a power problem. Report the smallest effect
    the 2022 cross-section could have detected.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import track1_investment, track2_weather_split, track3_med_sensitivity
from .shared import finite_sample as fs
from .shared import ingest
from .shared import reliability_metrics as rm
from .shared.io import save_results


def a1_heavy_tail(n_sims: int = 300, seed: int = 101) -> dict:
    """Re-derive track 3's sensitivity range with heavier-tailed daily SAIDI.

    Daily SAIDI is drawn from exp(t_nu * sigma / sqrt(nu/(nu-2))) instead of
    exp(normal * sigma), which keeps the log-scale dispersion but fattens both
    tails. The 1366 fitting procedure is unchanged: the utility still fits a
    log-normal, because that is what the standard tells it to do. Only reality
    is different.
    """
    rng = np.random.default_rng(seed)
    out = {}
    for nu in (3, 5, 10):
        scale = np.sqrt(nu / (nu - 2))
        for sigma in (1.0, 2.0, 3.0):
            realized = []
            for _ in range(n_sims):
                logs = rng.standard_t(nu, rm.DAYS_PER_YEAR * 5) / scale * sigma
                window = np.exp(logs)
                realized.append(
                    rm.simulate_med_exclusion(window[:rm.DAYS_PER_YEAR],
                                              window).retained_share)
            lognormal_r = float(fs.retained_share_fs(sigma).ravel()[0])
            out[f"nu{nu}_sigma{sigma}"] = {
                "heavy_tail_median_r": float(np.median(realized)),
                "lognormal_median_r": lognormal_r,
                "difference": float(np.median(realized) - lognormal_r),
            }
    diffs = [abs(v["difference"]) for v in out.values()]
    return {"by_case": out, "max_abs_shift_in_r": float(max(diffs)),
            "verdict": ("holding sigma fixed is the harsh version of this attack "
                        "and it lands hard. a1b_heavy_tail_matched is the fair "
                        "version: it re-inverts sigma under each distribution "
                        "so the model reproduces the SAME observed r, then "
                        "compares the beta sweep, which is what track 3 actually "
                        "claims")}


def _heavy_tail_r(nu: int, sigma: float, betas, rng, n_sims: int) -> np.ndarray:
    """Median realized retained share at each beta under t-tailed daily logs."""
    scale = np.sqrt(nu / (nu - 2))
    betas = np.asarray(betas, dtype=float)
    draws = np.empty((n_sims, betas.size))
    for i in range(n_sims):
        window = np.exp(rng.standard_t(nu, rm.DAYS_PER_YEAR * 5) / scale * sigma)
        year = window[:rm.DAYS_PER_YEAR]
        mu_hat, sigma_hat = rm.fit_lognormal(window)
        ys = np.sort(year)
        cum = np.concatenate([[0.0], np.cumsum(ys)])
        idx = np.searchsorted(ys, np.exp(mu_hat + betas * sigma_hat), side="right")
        draws[i] = cum[idx] / cum[-1]
    return np.median(draws, axis=0)


def a1b_heavy_tail_matched(target_r: float | None = None, n_sims: int = 250,
                           seed: int = 103) -> dict:
    """The attack track 3 actually has to survive.

    Track 3 never claims to know sigma. It claims that a utility-year reporting a
    given retained share would have reported some other value under a different
    beta. So the fair test re-calibrates sigma under the heavy-tailed process so
    that it reproduces the SAME observed retained share at beta = 2.5, and only
    then compares the beta sweep. If the sweep ratio survives, the headline is
    about the shape of the exclusion rule rather than about log-normality.
    """
    rng = np.random.default_rng(seed)
    from .shared import ingest as _ing
    if target_r is None:
        df = _ing.analysis_sample()
        adm = df["retained_share"][(df["retained_share"] > 0.03)
                                   & (df["retained_share"] < 0.99)]
        target_r = float(adm.median())

    betas = np.array([1.5, 2.0, 2.5, 3.0])
    out = {}

    sig_ln = float(fs.implied_sigma_fs(np.array([target_r]))[0])
    r_ln = fs.retained_share_fs(sig_ln, betas).ravel()
    out["lognormal"] = {
        "matched_sigma": sig_ln,
        "r_by_beta": {f"{b}": float(v) for b, v in zip(betas, r_ln)},
        "sweep_ratio_2_5_over_1_5": float(r_ln[2] / r_ln[0]),
    }

    for nu in (3, 5, 10):
        grid = np.arange(0.2, 6.01, 0.2)
        r25 = np.array([_heavy_tail_r(nu, g, [2.5], rng, 120)[0] for g in grid])
        order = np.argsort(r25)
        sig = float(np.interp(target_r, r25[order], grid[order]))
        r_ht = _heavy_tail_r(nu, sig, betas, rng, n_sims)
        out[f"t_nu{nu}"] = {
            "matched_sigma": sig,
            "r_by_beta": {f"{b}": float(v) for b, v in zip(betas, r_ht)},
            "sweep_ratio_2_5_over_1_5": float(r_ht[2] / r_ht[0])
                if r_ht[0] > 0 else None,
        }

    ratios = [v["sweep_ratio_2_5_over_1_5"] for v in out.values()
              if v["sweep_ratio_2_5_over_1_5"]]
    return {
        "target_retained_share": target_r,
        "by_distribution": out,
        "sweep_ratio_min": float(min(ratios)), "sweep_ratio_max": float(max(ratios)),
        "sweep_ratio_spread_x": float(max(ratios) / min(ratios)),
    }


def a2_mean_vs_median(n_sims: int = 400, seed: int = 102) -> dict:
    rng = np.random.default_rng(seed)
    rows = {}
    for sigma in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0):
        realized = []
        for _ in range(n_sims):
            w = rng.lognormal(0.0, sigma, rm.DAYS_PER_YEAR * 5)
            realized.append(rm.simulate_med_exclusion(w[:rm.DAYS_PER_YEAR],
                                                      w).retained_share)
        realized = np.array(realized)
        rows[f"sigma_{sigma}"] = {
            "median": float(np.median(realized)), "mean": float(realized.mean()),
            "mean_minus_median": float(realized.mean() - np.median(realized)),
        }
    gaps = [v["mean_minus_median"] for v in rows.values()]
    return {"by_sigma": rows, "max_gap": float(max(gaps)),
            "sigma_range_tested": [1.0, 6.0],
            "verdict": ("mean minus median is reported as measured over the "
                        "sigma range that the observed data actually implies; "
                        "the gap widens with sigma because a minority of years "
                        "contain no qualifying day and pin r at 1")}


def a3_bunching_specs() -> dict:
    df = ingest.analysis_sample()
    grid = {}
    for degree in (3, 4, 5, 7):
        for window in (0.02, 0.05, 0.10):
            for lo in (0.20, 0.30, 0.50):
                r = track3_med_sensitivity.excess_mass_at_zero_exclusion(
                    df, window=window, degree=degree, n_boot=150, fit_lo=lo)
                grid[f"deg{degree}_win{window}_lo{lo}"] = {
                    "excess_mass_ratio": r["excess_mass_ratio"],
                    "ci95": r["ci95"],
                }
    vals = [v["excess_mass_ratio"] for v in grid.values()
            if v["excess_mass_ratio"] is not None and np.isfinite(v["excess_mass_ratio"])]
    los = [v["ci95"][0] for v in grid.values() if np.isfinite(v["ci95"][0])]
    failing = {k: v for k, v in grid.items()
               if not np.isfinite(v["ci95"][0]) or v["ci95"][0] <= 1}
    return {
        "n_specifications": len(grid), "by_spec": grid,
        "min_excess_mass": float(min(vals)), "max_excess_mass": float(max(vals)),
        "median_excess_mass": float(np.median(vals)),
        "n_specs_with_ci_lower_above_1": int(sum(l > 1 for l in los)),
        "failing_specs": sorted(failing),
        "verdict": ("bunching survives iff the excess mass ratio stays above 1 "
                    "with the CI excluding 1 across every specification"),
    }


def a4_track2_trimmed(trim: float = 0.01) -> dict:
    """Track 2's headline, with extreme utilities removed and weighting dropped.

    Also re-run on the 2013-2018 consecutive window, which the seven-year panel
    made available. If the result only exists across the 2013-2022 endpoints it
    is an endpoint artefact.
    """
    years = track2_weather_split.ALL_YEARS
    df = track2_weather_split.balanced_panel(years)
    base = track2_weather_split.within_utility_decomposition(
        df, min(years), max(years))

    saidi = df["saidi_with"]
    lo, hi = saidi.quantile(trim), saidi.quantile(1 - trim)
    # drop a utility-state if ANY of its years is extreme. Keeping it when only
    # one year is in range (the first version of this attack) drops nobody and
    # makes the attack vacuous.
    outside = df.loc[(saidi < lo) | (saidi > hi), "utility_state"].unique()
    trimmed = df[~df["utility_state"].isin(outside)]
    n = trimmed.groupby("utility_state")["year"].nunique()
    trimmed = trimmed[trimmed["utility_state"].isin(n[n == len(years)].index)]
    tr = track2_weather_split.within_utility_decomposition(
        trimmed, min(years), max(years))

    cons = track2_weather_split.CONSECUTIVE
    consec = track2_weather_split.within_utility_decomposition(
        track2_weather_split.balanced_panel(cons), min(cons), max(cons))

    return {
        "baseline_share_from_excluded": base["share_of_change_from_excluded_part"],
        "trimmed_share_from_excluded": tr["share_of_change_from_excluded_part"],
        "n_baseline": base["n_utility_states"], "n_trimmed": tr["n_utility_states"],
        "unweighted_share_from_excluded": base["unweighted_share_from_excluded"],
        "consecutive_window_share_from_excluded":
            consec["share_of_change_from_excluded_part"],
        "consecutive_span": consec["span"],
        "trim": trim,
    }


def a5_ownership_large_only() -> dict:
    df = ingest.analysis_sample()
    med = df["customers"].median()
    big = df[df["customers"] >= med]
    huge = df[df["customers"] >= df["customers"].quantile(0.9)]
    out = {}
    for name, sub in (("all", df), ("above_median_size", big), ("top_decile", huge)):
        g = sub[sub["ownership_class"].isin(("IOU", "Coop", "Municipal"))]
        stats_ = g.groupby("ownership_class")["retained_share"].agg(
            ["count", "median", lambda x: float((x >= 1 - 1e-9).mean())])
        stats_.columns = ["n", "median_r", "share_zero_exclusion"]
        out[name] = {
            k: {kk: float(vv) for kk, vv in v.items()}
            for k, v in stats_.to_dict("index").items()
        }
        if {"IOU", "Coop"}.issubset(out[name]):
            out[name]["iou_minus_coop_median_r"] = (
                out[name]["IOU"]["median_r"] - out[name]["Coop"]["median_r"])
            out[name]["comparable"] = bool(
                out[name]["IOU"]["n"] >= 30 and out[name]["Coop"]["n"] >= 30)
    return out


def a6_track1_power() -> dict:
    """Track 1's null: could any of its three designs have seen an effect?

    A null is only informative if the design had power. Track 1 now reports a
    cross-section, a within-utility panel and a long difference, so this reports
    the minimum detectable effect for each and how much identifying variation
    each one had to work with. The cross-section's problem was never the
    estimator, it was that AMI stopped varying.
    """
    t1 = track1_investment.run(save=False)
    out = {"designs": {}}
    for year, res in t1["cross_sections"].items():
        c = res["coefficients"]["ami_share"]
        out["designs"][f"cross_section_{year}"] = {
            "beta": c["beta"], "se": c["se"], "ci95": c["ci95"],
            "mde_80pct_power": c["mde_80pct_power"],
            "mde_as_pct_saidi": c["mde_as_pct_saidi"],
            "ami_share_iqr": res["ami_share_iqr"],
            "share_at_100pct": res["share_at_100pct"],
        }
    w = t1["within_utility"]["coefficients"]["ami_share"]
    out["designs"]["within_utility_2016_2018"] = {
        "beta": w["beta"], "se": w["se"], "ci95": w["ci95"],
        "mde_80pct_power": w["mde_80pct_power"],
        "mde_as_pct_saidi": w["mde_as_pct_saidi"],
        "n_utilities_rolling_out": t1["within_utility"]["n_moving_ami_gt_0_50"],
    }
    ld = t1["long_difference"]["coefficients"]["d_ami"]
    out["designs"]["long_difference_2016_2018"] = {
        "beta": ld["beta"], "se": ld["se"], "ci95": ld["ci95"],
        "mde_80pct_power": ld["mde_80pct_power"],
        "mde_as_pct_saidi": ld["mde_as_pct_saidi"],
    }
    out["group_comparison"] = t1["long_difference"]["group_comparison"]
    out["verdict"] = ("every design agrees the effect is indistinguishable from "
                      "zero; the within-utility design is the one that had the "
                      "identifying variation to say so")
    return out


def a7_leave_one_state_out() -> dict:
    """Drop each state in turn and recompute every headline. **The attack the
    repository most needed and had not run.**

    Florida is the specific worry. Florida Power & Light files a 0.96 exclusion
    share on millions of customers, so any customer-weighted result could be a
    Florida result wearing a national label. Hurricane states more broadly carry
    most of the excluded minutes, and three of the four headlines here are
    customer-weighted.

    Four statistics are jackknifed, one per finding:
      Q1  the fleet sensitivity range across beta
      Q2  the excess mass at zero exclusion
      Q3  the share of large IOUs changing quartile in 2022
      Q4  the share of the 2013-2022 rise sitting in the excluded portion

    A finding survives if no single state's removal moves it outside the range
    the writeup claims. A finding fails if one state is carrying it.
    """
    df = ingest.analysis_sample()
    states = sorted(df["state"].unique())

    # Q4 works on the balanced panel; dropping a state leaves it balanced.
    panel = track2_weather_split.balanced_panel(track2_weather_split.ALL_YEARS)

    def stats_without(state: str | None) -> dict:
        sub = df if state is None else df[df["state"] != state]
        pan = panel if state is None else panel[panel["state"] != state]
        out = {}

        sens = track3_med_sensitivity.sensitivity(sub)
        out["fleet_range_ratio"] = sens["fleet_range_ratio"]
        out["fleet_saidi_at_2_5"] = sens["headline"]["beta_2.5"][
            "fleet_saidi_without_med"]

        try:
            out["excess_mass"] = track3_med_sensitivity.excess_mass_at_zero_exclusion(
                sub, n_boot=200)["excess_mass_ratio"]
        except Exception:
            out["excess_mass"] = np.nan

        rk = track3_med_sensitivity.ranking_sensitivity(sub)
        out["pct_changing_quartile_2022"] = rk["by_year"].get(2022, {}).get(
            "pct_changing_quartile", np.nan)

        if pan["utility_state"].nunique() > 50:
            wu = track2_weather_split.within_utility_decomposition(pan, 2013, 2022)
            out["share_from_excluded"] = wu["share_of_change_from_excluded_part"]
        else:
            out["share_from_excluded"] = np.nan
        return out

    base = stats_without(None)
    per_state = {st: stats_without(st) for st in states}

    summary = {}
    for key, baseline in base.items():
        vals = {st: v[key] for st, v in per_state.items()
                if v[key] is not None and np.isfinite(v[key])}
        if not vals:
            continue
        worst = max(vals, key=lambda k: abs(vals[k] - baseline))
        summary[key] = {
            "baseline": float(baseline),
            "min_leaving_one_out": float(min(vals.values())),
            "max_leaving_one_out": float(max(vals.values())),
            "most_influential_state": worst,
            "value_without_that_state": float(vals[worst]),
            "max_abs_shift": float(abs(vals[worst] - baseline)),
            "max_pct_shift": float(100 * abs(vals[worst] - baseline) / abs(baseline))
            if baseline else np.nan,
        }

    return {
        "n_states_dropped": len(states),
        "baseline": {k: float(v) for k, v in base.items()},
        "summary": summary,
        "florida": {k: float(v) for k, v in per_state.get("FL", {}).items()
                    if v is not None and np.isfinite(v)},
        "verdict": ("a headline survives if dropping any single state leaves it "
                    "inside the range the writeup claims; it fails if one state "
                    "is carrying it"),
    }


HURRICANE_STATES = track2_weather_split.HURRICANE_2017_STATES


def a8_stated_falsification_criterion(year: int = 2022,
                                      min_customers: int = 100_000) -> dict:
    """Run the criterion FINDINGS commits to, rather than leaving it rhetorical.

    FINDINGS states the repository's central claim as: measurement rules move
    reported distribution reliability more than the measured differences between
    utilities do. It names two ways that fails. Both are tested here.

    **Part 1.** Does the threshold sweep span materially less than the observed
    cross-utility spread in reported SAIDI? The comparison has to be
    like-for-like: one utility's own sweep across beta, against the spread
    between utilities at the threshold actually in force. If utilities differ
    from each other by more than the rule moves any one of them, the claim is
    backwards.

    **Part 2.** Does Q3's rank reversal disappear once utilities are compared
    within like storm exposure? If reversal is just storm-exposed utilities
    trading places with sheltered ones, it says nothing about measurement rules.

    Exposure is measured from 2013-2018 filings and applied to a later year, so
    the stratifier is not the outcome it is being used to explain.
    """
    df = ingest.analysis_sample()
    d = df[(df["year"] == year) & (df["ownership_class"] == "IOU")
           & (df["customers"] >= min_customers)].copy()

    betas = np.array([1.5, 2.5, 3.0])
    curve = fs.sensitivity_curve_fs(d["retained_share"].to_numpy(), betas)
    ok = np.isfinite(curve).all(axis=1)
    saidi_with = d["saidi_with"].to_numpy()
    own_sweep = ((saidi_with[ok] * curve[ok, 2])
                 / (saidi_with[ok] * curve[ok, 0]))
    reported = d["saidi_without"].to_numpy()
    spread = {f"p{hi}_over_p{lo}": float(np.percentile(reported, hi)
                                         / np.percentile(reported, lo))
              for lo, hi in ((10, 90), (25, 75), (5, 95))}
    part1 = {
        "n": int(len(d)), "n_admissible": int(ok.sum()),
        "own_sweep_median_x": float(np.median(own_sweep)),
        "own_sweep_iqr_x": [float(np.percentile(own_sweep, 25)),
                            float(np.percentile(own_sweep, 75))],
        "cross_utility_spread_x": spread,
        "rule_exceeds_p10_p90_spread": bool(
            np.median(own_sweep) > spread["p90_over_p10"]),
        "ratio_rule_to_spread": float(np.median(own_sweep)
                                      / spread["p90_over_p10"]),
    }

    pre = (df[df["year"].between(2013, 2018)]
           .groupby("utility_state")["excluded_share"].mean())
    d["pre_exposure"] = d["utility_state"].map(pre)

    def reversal(sub: pd.DataFrame):
        if len(sub) < 20:
            return None
        q_with = pd.qcut(sub["saidi_with"], 4, labels=False, duplicates="drop")
        q_without = pd.qcut(sub["saidi_without"], 4, labels=False,
                            duplicates="drop")
        rank_with = stats.rankdata(sub["saidi_with"])
        rank_without = stats.rankdata(sub["saidi_without"])
        return {
            "n": int(len(sub)),
            "spearman": float(stats.spearmanr(sub["saidi_with"],
                                              sub["saidi_without"]).statistic),
            "pct_changing_quartile": float(100 * (q_with != q_without).mean()),
            "median_rank_move": float(np.median(np.abs(rank_with - rank_without))),
        }

    cuts = d["pre_exposure"].quantile([1 / 3, 2 / 3]).values
    strata = {
        "pooled": d,
        "hurricane_track_states": d[d["state"].isin(HURRICANE_STATES)],
        "non_hurricane_states": d[~d["state"].isin(HURRICANE_STATES)],
        "low_pre_exposure": d[d["pre_exposure"] <= cuts[0]],
        "mid_pre_exposure": d[(d["pre_exposure"] > cuts[0])
                              & (d["pre_exposure"] <= cuts[1])],
        "high_pre_exposure": d[d["pre_exposure"] > cuts[1]],
    }
    by_stratum = {k: reversal(v) for k, v in strata.items()}
    usable = {k: v for k, v in by_stratum.items()
              if v is not None and k != "pooled"}
    base = by_stratum["pooled"]["pct_changing_quartile"]
    part2 = {
        "by_stratum": by_stratum,
        "pooled_pct_changing_quartile": base,
        "min_within_stratum": float(min(v["pct_changing_quartile"]
                                        for v in usable.values())),
        "max_within_stratum": float(max(v["pct_changing_quartile"]
                                        for v in usable.values())),
        "survives": bool(min(v["pct_changing_quartile"]
                             for v in usable.values()) > 0.6 * base),
        "statistic_note": (
            "quartile change is the comparable statistic across strata; median "
            "rank move is not, because it scales with the size of the field and "
            "falls mechanically when a stratum is smaller"),
    }

    return {
        "year": year, "min_customers": min_customers,
        "part1_rule_vs_cross_utility_spread": part1,
        "part2_reversal_within_exposure": part2,
        "criterion_met": bool(part1["rule_exceeds_p10_p90_spread"]
                              and part2["survives"]),
        "verdict": ("the criterion FINDINGS commits to; both halves must hold "
                    "or the repository's central claim is overstated"),
    }


def a9_leave_one_utility_out(year: int = 2022) -> dict:
    """Named in FALSIFICATION as not run, so run it.

    A7 works at state granularity. Q4 and Q8 both lean on Florida, and inside
    Florida a single co-operative reported over nine days of outage per customer
    after Hurricane Ian. Drop the largest single contributors to national
    customer-outage-minutes and recompute Q8's aggregation spread.
    """
    from . import track9_aggregation as t9

    df = ingest.analysis_sample()
    d = df[df["year"] == year].copy()
    d["contribution"] = d["saidi_with"] * d["customers"]
    ordered = d.sort_values("contribution", ascending=False)

    rows = {}
    for k in (0, 1, 3, 5, 10):
        sub = d if k == 0 else d[~d.index.isin(ordered.index[:k])]
        agg = t9.aggregators(sub["saidi_with"].to_numpy(),
                             sub["customers"].to_numpy())
        rows[f"drop_top_{k}"] = {
            "n": int(len(sub)),
            "spread_x": float(max(agg.values()) / min(agg.values())),
            "customer_weighted_mean": agg["customer_weighted_mean"],
            "median_utility": agg["median_utility"],
        }
    top = ordered.iloc[0]
    return {
        "year": year,
        "largest_contributor": {
            "state": top["state"],
            "saidi_with": float(top["saidi_with"]),
            "customers": int(top["customers"]),
            "share_of_national_customer_minutes": float(
                top["contribution"] / d["contribution"].sum()),
        },
        "by_drop": rows,
        "spread_survives_dropping_top_1": bool(
            rows["drop_top_1"]["spread_x"] > 1.5),
        "spread_survives_dropping_top_10": bool(
            rows["drop_top_10"]["spread_x"] > 1.5),
        "note": ("the utility is identified by state and size rather than name, "
                 "since the point is the concentration, not the utility"),
    }


def _tail_surface(nu: float | None, sigma_grid: np.ndarray, betas: np.ndarray,
                  n_sims: int, rng: np.random.Generator) -> np.ndarray:
    """Median realized retained share on a (sigma, beta) grid.

    nu=None is the log-normal IEEE 1366 assumes. Otherwise daily log-SAIDI is a
    Student-t with nu degrees of freedom, rescaled so its standard deviation is
    still sigma. Either way the utility follows the standard: it fits a
    log-normal to five years of logs and excludes days above
    exp(mu_hat + beta * sigma_hat). Only reality changes, never the procedure.
    """
    days, window = rm.DAYS_PER_YEAR, rm.DAYS_PER_YEAR * 5
    out = np.empty((sigma_grid.size, betas.size))
    for i, sigma in enumerate(sigma_grid):
        if nu is None:
            z = rng.standard_normal((n_sims, window))
        else:
            z = rng.standard_t(nu, (n_sims, window)) / np.sqrt(nu / (nu - 2))
        logs = z * sigma
        mu_hat = logs.mean(axis=1, keepdims=True)
        sd_hat = logs.std(axis=1, ddof=1, keepdims=True)
        year = np.exp(logs[:, :days])
        total = year.sum(axis=1)
        for j, b in enumerate(betas):
            kept = np.where(logs[:, :days] <= mu_hat + b * sd_hat, year, 0.0)
            out[i, j] = np.median(kept.sum(axis=1) / total)
    return np.minimum.accumulate(out, axis=0)  # r is non-increasing in sigma


def a10_tail_breaking_point(year: int = 2022, min_customers: int = 100_000,
                            n_sims: int = 250, seed: int = 110) -> dict:
    """How heavy do daily outage tails have to be before A8 part one fails?

    A8 found the threshold moves one large utility's own reported SAIDI by a
    median of 6.18x, against a 3.92x spread between utilities. But the 6.18x is
    model-implied under log-normal daily SAIDI, and A1 showed the sweep narrows
    under heavier tails. So the central claim has a breaking point, and this
    finds it.

    Fair version, as in A1b: for each tail weight, every utility's dispersion is
    re-inverted so that the model reproduces the retained share that utility
    actually filed at beta = 2.5. Only then is its own sweep from beta 1.5 to 3.0
    computed. The cross-utility spread it is compared against is observed data
    and does not change with the model.
    """
    rng = np.random.default_rng(seed)
    df = ingest.analysis_sample()
    d = df[(df["year"] == year) & (df["ownership_class"] == "IOU")
           & (df["customers"] >= min_customers)]
    r_obs = d["retained_share"].to_numpy()
    reported = d["saidi_without"].to_numpy()
    spread = float(np.percentile(reported, 90) / np.percentile(reported, 10))

    betas = np.array([1.5, 2.5, 3.0])
    sigma_grid = np.round(np.arange(0.1, 6.01, 0.1), 3)
    rows = {}
    for label, nu in (("lognormal", None), ("t_nu30", 30.0), ("t_nu15", 15.0),
                      ("t_nu10", 10.0), ("t_nu7", 7.0), ("t_nu5", 5.0),
                      ("t_nu3", 3.0)):
        surf = _tail_surface(nu, sigma_grid, betas, n_sims, rng)
        r25 = surf[:, 1]
        order = np.argsort(r25)
        inside = (r_obs >= r25.min()) & (r_obs <= r25.max())
        sig = np.interp(r_obs[inside], r25[order], sigma_grid[order])
        r15 = np.interp(sig, sigma_grid, surf[:, 0])
        r30 = np.interp(sig, sigma_grid, surf[:, 2])
        sweep = r30 / np.clip(r15, 1e-9, None)
        rows[label] = {
            "nu": nu,
            "n_representable": int(inside.sum()),
            "median_own_sweep_x": float(np.median(sweep)),
            "ratio_to_cross_utility_spread": float(np.median(sweep) / spread),
            "claim_holds": bool(np.median(sweep) > spread),
        }

    holds = [k for k, v in rows.items() if v["claim_holds"]]
    fails = [k for k, v in rows.items() if not v["claim_holds"]]
    heaviest_holding = min((rows[k]["nu"] for k in holds if rows[k]["nu"]),
                           default=None)
    lightest_failing = max((rows[k]["nu"] for k in fails if rows[k]["nu"]),
                           default=None)
    return {
        "year": year,
        "cross_utility_spread_p90_p10": spread,
        "by_tail": rows,
        "holds_under": holds,
        "fails_under": fails,
        "breaking_point_nu_between": [lightest_failing, heaviest_holding],
        "reading": ("the central claim is conditional on daily outage tails; "
                    "it holds for tails no heavier than the breaking point and "
                    "fails beyond it. Which side reality is on needs daily "
                    "SAIDI, which is not public at national scale"),
    }


def run(save: bool = True) -> dict:
    out = {
        "A1_heavy_tail": a1_heavy_tail(),
        "A1b_heavy_tail_matched": a1b_heavy_tail_matched(),
        "A2_mean_vs_median": a2_mean_vs_median(),
        "A3_bunching_specs": a3_bunching_specs(),
        "A4_track2_trimmed": a4_track2_trimmed(),
        "A5_ownership_large_only": a5_ownership_large_only(),
        "A6_track1_power": a6_track1_power(),
        "A7_leave_one_state_out": a7_leave_one_state_out(),
        "A8_stated_falsification_criterion": a8_stated_falsification_criterion(),
        "A9_leave_one_utility_out": a9_leave_one_utility_out(),
        "A10_tail_breaking_point": a10_tail_breaking_point(),
    }
    if save:
        save_results("track8_falsification", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
