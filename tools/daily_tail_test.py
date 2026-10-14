#!/usr/bin/env python3
"""Test the assumption every model-implied result here rests on, on real data.

    python tools/daily_tail_test.py daily.csv                  # date, customer_minutes
    python tools/daily_tail_test.py eaglei_outages_2021.csv --eaglei --state MA
    python tools/daily_tail_test.py eaglei_outages_2021.csv --eaglei --fips 25025
    python tools/daily_tail_test.py --archive pge --series excl_psps   # vendored

IEEE 1366 assumes daily SAIDI is log-normal. Attacks A10 to A13 show the
repository's model-implied comparison survives only if that is close to true.
Attack A14 now runs this test on the only daily data found, two utilities'
outage maps archived by git scraping (data/daily/), and log-normality fails for
both. This tool runs the same code on any other daily series, including raw
EAGLE-I county files, so the result can be checked against more utilities. It
was validated on synthetic series in the test suite before any real data arrived.

What it reports, on the positive daily values (zero days are dropped, as IEEE
1366 does when fitting):

  shape of log daily values   skewness, excess kurtosis, Shapiro-Wilk p-value
  which tail family fits      normal vs Laplace vs Student-t by AIC on the logs.
                              Normal and Laplace are closed-form fits; Student-t
                              is profiled over a fixed grid of degrees of
                              freedom by EM, because scipy's general optimizer
                              stops at poor local optima on real outage data
                              and the answer has to reproduce exactly.
  Hill tail index             of the level, on the top 5% of days. Reported, but
                              NOT diagnostic on its own: a wide log-normal gives
                              a finite Hill index inside Ahmad & Dobson's 0.73
                              to 1.47 too (1.23 at sigma 1.8 in this tool's own
                              validation). Read the tail family and kurtosis.
  major event days per year   days above exp(mean + 2.5 * sd) of logs, per
                              observed day, against the standard's nominal 2.27
                              and the working group's observed two to eight

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
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blinkrate.shared.daily import (NOMINAL_MED_PER_YEAR, SERIES,  # noqa: E402
                                    hill_alpha, observed_days, tail_family,
                                    tail_shape)

__all__ = ["analyse", "best_tail_family", "hill_alpha", "tail_family"]

NOMINAL_PER_YEAR = NOMINAL_MED_PER_YEAR
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


def best_tail_family(logs: np.ndarray) -> dict:
    """Kept for callers of the earlier interface; see blinkrate.shared.daily."""
    return tail_family(logs)


def analyse(daily: pd.Series) -> dict:
    daily = daily[daily.index.notna()]
    core = tail_shape(daily.to_numpy(float))
    if core["n_positive_days"] < 60:
        raise SystemExit(f"only {core['n_positive_days']} positive days; need at least 60")
    family, kurt, sw_p = core["tail_family"], core["log_excess_kurtosis"], \
        core["shapiro_wilk_p"]
    alpha = core["hill_alpha_top_5pct"]
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
    span = max((daily.index.max() - daily.index.min()).days / 365.25, 1 / 365.25)
    return {
        "n_days": core["n_days"],
        "n_positive_days": core["n_positive_days"],
        "share_zero_days": float((daily <= 0).mean()),
        "years_covered": float(span),
        "log_skewness": core["log_skewness"],
        "log_excess_kurtosis": kurt,
        "shapiro_wilk_p": sw_p,
        "tail_family": family,
        "hill_alpha_top_5pct": alpha,
        "hill_alpha_within_ahmad_dobson": bool(
            AHMAD_DOBSON_ALPHA[0] <= alpha <= AHMAD_DOBSON_ALPHA[1]),
        "med_days_per_year_at_2_5": core["med_days_per_year_at_2_5"],
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
    ap.add_argument("path", nargs="?", help="daily CSV or raw EAGLE-I file")
    ap.add_argument("--archive", choices=sorted(SERIES),
                    help="use a vendored outage-map series from data/daily/")
    ap.add_argument("--series", default="all",
                    help="with --archive: all, excl_psps or unplanned (PG&E)")
    ap.add_argument("--eaglei", action="store_true",
                    help="input is a raw EAGLE-I county file")
    ap.add_argument("--state", help="EAGLE-I: two-letter state or full name")
    ap.add_argument("--fips", help="EAGLE-I: five-digit county FIPS code")
    ap.add_argument("--json", action="store_true", help="print JSON only")
    args = ap.parse_args()

    if args.archive:
        obs = observed_days(args.archive, args.series)
        daily = pd.Series(obs.to_numpy(float), index=pd.to_datetime(obs.index))
    elif args.path:
        daily = (daily_from_eaglei(args.path, args.state, args.fips) if args.eaglei
                 else daily_from_csv(args.path))
    else:
        ap.error("give a file path or --archive")
    out = analyse(daily)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    f = out["tail_family"]
    print(f"{out['n_positive_days']} positive days spanning {out['years_covered']:.1f} "
          f"years ({100 * out['share_zero_days']:.1f}% zero)")
    print(f"log skewness {out['log_skewness']:+.2f}, excess kurtosis "
          f"{out['log_excess_kurtosis']:+.2f}, Shapiro-Wilk p {out['shapiro_wilk_p']:.3g}")
    print(f"best tail family by AIC: {f['best']} (Student-t profile best at "
          f"df {f['student_t_df']:g})")
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
