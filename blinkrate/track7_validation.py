"""Track 7 - validation, before tracks 1-6 are allowed to lean on any of this.

Three checks, none of which is a finding:

1. CAIDI identity in the source. CAIDI = SAIDI / SAIFI by definition, and the
   2022 file reports all three independently. Any utility-year where the
   reported CAIDI does not reproduce is a filing error, and the rate of those
   errors is the honest error bar on everything downstream.

2. Closed form against procedure. r = Phi(beta - sigma) is a ratio of
   expectations; a filed utility-year is one realization. This measures the gap
   directly by simulating the 1366 procedure and comparing.

3. Round trip. Take a reported retained share, invert it to sigma, simulate
   fresh years at that sigma, and check the simulated retained share comes back
   to where it started. If the inversion is right this closes; if the calibration
   grid is too coarse or the median statistic is doing something odd, it will not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .shared import finite_sample as fs
from .shared import ingest
from .shared import reliability_metrics as rm
from .shared.io import save_results


CAIDI_YEARS = (2016, 2017, 2018, 2022)


def caidi_identity(tolerance: float = 0.01) -> dict:
    """Does reported CAIDI equal reported SAIDI / SAIFI?

    CAIDI is definitionally SAIDI / SAIFI, and EIA-861 collects all three
    independently, so any filing where the identity fails is an arithmetic error
    in the source. The rate of those errors is the honest error bar on
    everything downstream.

    Run on every year that carries a CAIDI column. The 2013-2015 files do not,
    so they cannot be checked this way and their arithmetic is validated only by
    the with/without ordering constraint in the ingest filter.
    """
    df = pd.concat([ingest.load_year(y) for y in CAIDI_YEARS], ignore_index=True)
    rows = []
    for block in ("ieee", "other"):
        sub = df[[f"{block}_saidi_with", f"{block}_saifi_with", f"{block}_caidi_with",
                  f"{block}_saidi_without", f"{block}_saifi_without",
                  f"{block}_caidi_without"]].copy()
        sub.columns = ["saidi_w", "saifi_w", "caidi_w",
                       "saidi_wo", "saifi_wo", "caidi_wo"]
        sub["block"] = block
        rows.append(sub)
    d = pd.concat(rows, ignore_index=True)

    out = {}
    for tag, (sa, sf, ca) in {
        "with_med": ("saidi_w", "saifi_w", "caidi_w"),
        "without_med": ("saidi_wo", "saifi_wo", "caidi_wo"),
    }.items():
        m = d.dropna(subset=[sa, sf, ca])
        m = m[(m[sf] > 0) & (m[ca] > 0)]
        implied = m[sa] / m[sf]
        rel = (implied - m[ca]).abs() / m[ca]
        out[tag] = {
            "n_checked": int(len(m)),
            "share_within_tolerance": float((rel <= tolerance).mean()),
            "median_relative_error": float(rel.median()),
            "p99_relative_error": float(rel.quantile(0.99)),
            "n_failing": int((rel > tolerance).sum()),
        }
    out["tolerance"] = tolerance
    out["years_checked"] = list(CAIDI_YEARS)
    return out


def closed_form_vs_procedure(sigmas=(0.5, 1.0, 1.5, 2.0, 2.5, 3.0),
                             n_sims: int = 400, seed: int = 11) -> dict:
    rng = np.random.default_rng(seed)
    rows = {}
    for sigma in sigmas:
        realized = []
        for _ in range(n_sims):
            window = rng.lognormal(0.0, sigma, rm.DAYS_PER_YEAR * 5)
            res = rm.simulate_med_exclusion(window[:rm.DAYS_PER_YEAR], window)
            realized.append(res.retained_share)
        realized = np.array(realized)
        cf = float(rm.retained_share_closed_form(sigma))
        cal = float(fs.retained_share_fs(sigma).ravel()[0])
        rows[f"sigma_{sigma}"] = {
            "closed_form": cf,
            "simulated_median": float(np.median(realized)),
            "simulated_mean": float(realized.mean()),
            "calibrated_surface": cal,
            "abs_err_closed_form_vs_sim_median": abs(cf - float(np.median(realized))),
            "abs_err_calibration_vs_sim_median": abs(cal - float(np.median(realized))),
        }
    errs_cf = [v["abs_err_closed_form_vs_sim_median"] for v in rows.values()]
    errs_cal = [v["abs_err_calibration_vs_sim_median"] for v in rows.values()]
    return {
        "by_sigma": rows,
        "max_abs_err_closed_form": float(max(errs_cf)),
        "max_abs_err_calibration": float(max(errs_cal)),
        "verdict": ("closed form is accurate for sigma <= 1 and degrades badly "
                    "above 2; the calibrated surface is what the tracks use"),
    }


def round_trip(retained_shares=(0.95, 0.85, 0.75, 0.60, 0.45, 0.30),
               n_sims: int = 400, seed: int = 13) -> dict:
    rng = np.random.default_rng(seed)
    rows = {}
    for r in retained_shares:
        sigma = float(fs.implied_sigma_fs(np.array([r]))[0])
        realized = []
        for _ in range(n_sims):
            window = rng.lognormal(0.0, sigma, rm.DAYS_PER_YEAR * 5)
            realized.append(
                rm.simulate_med_exclusion(window[:rm.DAYS_PER_YEAR],
                                          window).retained_share)
        rows[f"r_{r}"] = {
            "implied_sigma": sigma,
            "recovered_median_r": float(np.median(realized)),
            "abs_error": abs(r - float(np.median(realized))),
        }
    return {"by_r": rows,
            "max_abs_error": float(max(v["abs_error"] for v in rows.values()))}


def hand_checks(n: int = 10, seed: int = 3) -> dict:
    """Arithmetic spot check: recompute the derived columns from raw fields."""
    df = ingest.analysis_sample().sample(n, random_state=seed)
    bad = []
    for _, r in df.iterrows():
        exp_excluded = r["saidi_with"] - r["saidi_without"]
        exp_retained = r["saidi_without"] / r["saidi_with"]
        if (abs(exp_excluded - r["excluded_minutes"]) > 1e-9
                or abs(exp_retained - r["retained_share"]) > 1e-12):
            bad.append(int(r["utility_id"]))
    return {"n_checked": int(n), "n_mismatched": len(bad), "mismatched_ids": bad}


def run(save: bool = True) -> dict:
    out = {
        "caidi_identity": caidi_identity(),
        "closed_form_vs_procedure": closed_form_vs_procedure(),
        "round_trip": round_trip(),
        "hand_checks": hand_checks(),
        "rejected_rows": {
            "n": int(len(ingest.rejected_rows())),
            "by_reason": ingest.rejected_rows()["reject_reason"]
            .value_counts().to_dict(),
        },
        "duplicate_filings": {
            "n_rows_involved": int(len(ingest.duplicate_filings())),
            "note": ("genuine duplicate utility-state-year filings in the 2014 "
                     "source; the larger-customer-count filing is kept"),
        },
    }
    if save:
        save_results("track7_validation", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
