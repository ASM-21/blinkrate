#!/usr/bin/env python3
"""Test the assumption every model-implied result here rests on, on real data.

    python tools/daily_tail_test.py daily.csv                  # date, customer_minutes
    python tools/daily_tail_test.py eaglei_outages_2021.csv --eaglei --state MA
    python tools/daily_tail_test.py eaglei_outages_2021.csv --eaglei --fips 25025

IEEE 1366 assumes daily SAIDI is log-normal. Attacks A10 to A13 show the
repository's model-implied comparison survives only if that is close to true,
and the only US tail measurement found (Ahmad & Dobson 2025, event level) points
to Laplace-like tails in the log, under which it fails. Daily outage data would
settle it. None is reachable from the environment this repository was built in,
so this tool exists to turn "someone should test this" into one command, and it
is validated on synthetic series in the test suite before any real data arrives.

What it reports, on the positive daily values (zero days are dropped, as IEEE
1366 does when fitting):

  shape of log daily values   skewness, excess kurtosis, Shapiro-Wilk p-value
  which tail family fits      normal vs Laplace vs Student-t by AIC on the logs
  Hill tail index             of the level, on the top 5% of days. Reported, but
                              NOT diagnostic on its own: a wide log-normal gives
                              a finite Hill index inside Ahmad & Dobson's 0.73
                              to 1.47 too (1.23 at sigma 1.8 in this tool's own
                              validation). Read the tail family and kurtosis.
  major event days per year   days above exp(mean + 2.5 * sd) of logs, against
                              the standard's nominal 2.27 and the working
                              group's observed two to eight

Scale does not matter. Customer-minutes and SAIDI differ by a constant (the
customer count), which shifts the logs without changing their shape, so a
customer-minutes series tests the SAIDI assumption directly.

EAGLE-I CAVEATS, stated because they bias the answer. County customers-out at
15-minute intervals only approximates customer-minutes interrupted: it follows
utility outage-map cadence and misses momentary events. EAGLE-I also omits
zero rows and does not distinguish a zero from a collection gap, so the zero-day
share it produces is not trustworthy, and gaps inside an outage shorten it.
Treat an EAGLE-I result as evidence about tail shape, not as SAIDI.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

BETA = 2.5
NOMINAL_PER_YEAR = 365 * stats.norm.sf(BETA)
WG_OBSERVED = (2.0, 8.0)
AHMAD_DOBSON_ALPHA = (0.73, 1.47)
INTERVAL_MINUTES = 15


def daily_from_eaglei(path: str, state: str | None, fips: str | None) -> pd.Series:
    """EAGLE-I rows are customers out per county per 15 minutes."""
    usecols = ["fips_code", "state", "customers_out", "run_start_time"]
    df = pd.read_csv(path, usecols=lambda c: c.lower() in usecols)
    df.columns = [c.lower() for c in df.columns]
    if state:
        wanted = {state.upper(), _STATE_NAMES.get(state.upper(), "").upper()}
        df = df[df["state"].astype(str).str.upper().isin(wanted - {""})]
    if fips:
        df = df[df["fips_code"].astype(str).str.zfill(5) == str(fips).zfill(5)]
    if df.empty:
        raise SystemExit("no EAGLE-I rows match that filter")
    day = pd.to_datetime(df["run_start_time"], utc=True).dt.floor("D")
    cmi = df["customers_out"].astype(float) * INTERVAL_MINUTES
    return cmi.groupby(day).sum().sort_index()


def daily_from_csv(path: str) -> pd.Series:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date") or df.columns[0]
    val_col = (cols.get("customer_minutes") or cols.get("saidi")
               or cols.get("cmi") or df.columns[1])
    s = pd.Series(df[val_col].astype(float).to_numpy(),
                  index=pd.to_datetime(df[date_col]))
    return s.groupby(s.index.floor("D")).sum().sort_index()


def hill_alpha(values: np.ndarray, top_share: float = 0.05) -> float:
    """Hill estimator of the upper tail index of the level, on the top k."""
    x = np.sort(values[values > 0])[::-1]
    k = max(int(len(x) * top_share), 10)
    if len(x) <= k:
        return float("nan")
    logs = np.log(x[:k]) - np.log(x[k])
    return float(1.0 / logs.mean()) if logs.mean() > 0 else float("nan")


def best_tail_family(logs: np.ndarray) -> dict:
    """AIC for normal, Laplace and Student-t fitted to the log values."""
    fits = {}
    mu, sd = logs.mean(), logs.std(ddof=1)
    fits["normal"] = (2 * 2 - 2 * stats.norm.logpdf(logs, mu, sd).sum())
    loc, scale = stats.laplace.fit(logs)
    fits["laplace"] = (2 * 2 - 2 * stats.laplace.logpdf(logs, loc, scale).sum())
    df_t, loc_t, scale_t = stats.t.fit(logs)
    fits["student_t"] = (2 * 3 - 2 * stats.t.logpdf(logs, df_t, loc_t, scale_t).sum())
    best = min(fits, key=fits.get)
    return {"aic": {k: float(v) for k, v in fits.items()}, "best": best,
            "student_t_df": float(df_t)}


def analyse(daily: pd.Series) -> dict:
    daily = daily[daily.index.notna()]
    positive = daily[daily > 0]
    if len(positive) < 60:
        raise SystemExit(f"only {len(positive)} positive days; need at least 60")
    logs = np.log(positive.to_numpy())
    mu, sd = logs.mean(), logs.std(ddof=1)
    n_years = max((daily.index.max() - daily.index.min()).days / 365.25, 1 / 365.25)
    exceed = int((logs > mu + BETA * sd).sum())
    per_year = exceed / n_years
    sw_sample = logs if len(logs) <= 5000 else np.random.default_rng(0).choice(
        logs, 5000, replace=False)
    family = best_tail_family(logs)
    alpha = hill_alpha(positive.to_numpy())

    sw_p = float(stats.shapiro(sw_sample).pvalue)
    kurt = float(stats.kurtosis(logs))
    if family["best"] == "normal" and sw_p < 0.01 and abs(kurt) > 0.5:
        verdict = ("none of the three families fits well: log-normal is closest "
                   "by AIC but normality is rejected, so the model-implied "
                   "results should not be read as confirmed for this series")
    elif family["best"] == "normal":
        verdict = ("log-normal is the best-fitting family: the model-implied "
                   "results are on their own assumption here")
    else:
        verdict = (f"{family['best']} fits better than log-normal: under the "
                   "repository's attacks A12 and A13 the model-implied central "
                   "comparison fails for tails like these")
    return {
        "n_days": int(len(daily)),
        "n_positive_days": int(len(positive)),
        "share_zero_days": float((daily <= 0).mean()),
        "years_covered": float(n_years),
        "log_skewness": float(stats.skew(logs)),
        "log_excess_kurtosis": kurt,
        "shapiro_wilk_p": sw_p,
        "tail_family": family,
        "hill_alpha_top_5pct": alpha,
        "hill_alpha_within_ahmad_dobson": bool(
            AHMAD_DOBSON_ALPHA[0] <= alpha <= AHMAD_DOBSON_ALPHA[1]),
        "med_days_per_year_at_2_5": float(per_year),
        "nominal_med_days_per_year": float(NOMINAL_PER_YEAR),
        "working_group_observed": list(WG_OBSERVED),
        "verdict": verdict,
        "caveat": ("threshold fitted on the whole series rather than IEEE 1366's "
                   "rolling five years, so non-stationarity is not separated from "
                   "tail shape"),
    }


_STATE_NAMES = {"MA": "Massachusetts", "PA": "Pennsylvania", "NY": "New York",
                "CA": "California", "TX": "Texas", "FL": "Florida",
                "MD": "Maryland", "IL": "Illinois"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--eaglei", action="store_true",
                    help="input is a raw EAGLE-I county file")
    ap.add_argument("--state", help="EAGLE-I: two-letter state or full name")
    ap.add_argument("--fips", help="EAGLE-I: five-digit county FIPS code")
    ap.add_argument("--json", action="store_true", help="print JSON only")
    args = ap.parse_args()

    daily = (daily_from_eaglei(args.path, args.state, args.fips) if args.eaglei
             else daily_from_csv(args.path))
    out = analyse(daily)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    f = out["tail_family"]
    print(f"{out['n_positive_days']} positive days over {out['years_covered']:.1f} "
          f"years ({100 * out['share_zero_days']:.1f}% zero)")
    print(f"log skewness {out['log_skewness']:+.2f}, excess kurtosis "
          f"{out['log_excess_kurtosis']:+.2f}, Shapiro-Wilk p {out['shapiro_wilk_p']:.3g}")
    print(f"best tail family by AIC: {f['best']} (Student-t fit df "
          f"{f['student_t_df']:.1f})")
    print(f"Hill alpha, top 5%: {out['hill_alpha_top_5pct']:.2f} "
          f"(Ahmad & Dobson measured {AHMAD_DOBSON_ALPHA[0]} to "
          f"{AHMAD_DOBSON_ALPHA[1]}; not diagnostic alone, a wide "
          "log-normal lands in that range too)")
    print(f"major event days per year at beta 2.5: "
          f"{out['med_days_per_year_at_2_5']:.2f} (nominal "
          f"{out['nominal_med_days_per_year']:.2f}, working group observed "
          f"{WG_OBSERVED[0]:.0f} to {WG_OBSERVED[1]:.0f})")
    print(f"\n{out['verdict']}\n{out['caveat']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
