"""Daily outage series from public outage-map archives, and the tests run on them.

Every model-implied number in this repository rests on IEEE 1366's assumption
that daily SAIDI is log-normal, and EIA-861 publishes no daily data to test it
with. Two utilities' outage maps were archived in public by git scraping, a
snapshot of customers out every ten minutes or so: PG&E from June 2019 to April
2022, and FPL by county from September 2019 to January 2023.
`tools/build_outage_snapshots.py` rebuilds `data/daily/` from those archives at
pinned commits. This module turns the snapshots into daily customer-minutes and
implements the measurements attack A14 reports.

What these series are, and are not. Customers out on an outage map is an
operational estimate refreshed every few minutes, not the interruption record a
utility reports under IEEE 1366. It misses momentary interruptions, can include
customers whose outage the utility later excludes, and follows the map's own
cadence. For FPL 2022, the one utility-year with both a filing and a full year of
map data, the map runs above the filing (A14 reports by how much). So these
series test the shape of daily outage burden and how the exclusion rule acts on
it, not the level of reported SAIDI.

Everything here is deterministic and free of iterative optimizers with
convergence tests, because results are stored to nine significant figures and
must reproduce byte for byte on any runner. Normal and Laplace fits are closed
form. Student-t is fitted by EM at fixed degrees of freedom with a fixed number
of iterations, profiled over a fixed grid, rather than by scipy's general
optimizer, which also stops at poor local optima on these data.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import stats

DATA = Path(__file__).resolve().parents[2] / "data" / "daily"

UTILITIES = {
    "pge": {"name": "PG&E", "file": "pge_outage_map_snapshots.csv",
            "tz": "America/Los_Angeles", "eia_id": 14328, "state": "CA",
            "archive": "github.com/simonw/pge-outages-pre-2024",
            "commit": "d1561539277a42890b85bb57f97f5bc8598c5454"},
    "fpl": {"name": "FPL", "file": "fpl_outage_map_snapshots.csv",
            "tz": "America/New_York", "eia_id": 6452, "state": "FL",
            "archive": "github.com/simonw/disaster-data",
            "commit": "6ab407fc8a2e42809c6fa80b57b992b40e0895bf"},
}

# Customer-minute series per utility: name -> how to compute customers out.
SERIES = {
    "pge": {"all": ("customers_out",),
            "excl_psps": ("customers_out", "-psps"),
            "unplanned": ("customers_out", "-psps", "-planned")},
    "fpl": {"all": ("customers_out",)},
}

# A silence longer than this is a gap in observation rather than a quiet spell:
# the scraper commits whenever anything on the map changes, and with dozens of
# open outages that happens every few minutes. A gap contributes nothing and
# lowers the day's coverage.
MAX_GAP_S = 3 * 3600
# A day counts only if at least this share of it was observed.
MIN_COVERAGE = 0.9

BETA = 2.5
NOMINAL_MED_PER_YEAR = 365 * stats.norm.sf(BETA)


def load_snapshots(key: str) -> pd.DataFrame:
    return pd.read_csv(DATA / UTILITIES[key]["file"])


def _local_midnights(t0: int, t1: int, tz: ZoneInfo) -> tuple[list, np.ndarray]:
    first = datetime.fromtimestamp(t0, tz).date()
    last = datetime.fromtimestamp(t1, tz).date()
    days = [first + timedelta(days=i) for i in range((last - first).days + 2)]
    edges = np.array([int(datetime.combine(d, time(0), tz).timestamp()) for d in days],
                     dtype=np.int64)
    return days[:-1], edges


def integrate(t: np.ndarray, weights: dict, tz: ZoneInfo,
              max_gap_s: int = MAX_GAP_S) -> pd.DataFrame:
    """Integrate step functions of time into local calendar days, in integers.

    t holds strictly increasing Unix seconds; each array in weights holds the
    value in force from that snapshot until the next. An interval longer than
    max_gap_s is unobserved: it adds nothing and lowers coverage. Days are
    local calendar days, 23 or 25 hours long at daylight-saving changes. Returns
    one column of weight-seconds per weight, plus `observed_s`, `day_s`,
    `coverage` and `snapshots`, indexed by local date.
    """
    t = np.asarray(t, dtype=np.int64)
    if np.any(np.diff(t) <= 0):
        raise ValueError("snapshot times must be strictly increasing")
    if max_gap_s >= 86400:
        raise ValueError("max_gap_s must be under a day so an interval crosses "
                         "at most one midnight")
    days, edges = _local_midnights(int(t[0]), int(t[-1]), tz)
    a, b = t[:-1], t[1:]
    keep = (b - a) <= max_gap_s
    a, b = a[keep], b[keep]
    i0 = np.searchsorted(edges, a, side="right") - 1
    cut = np.minimum(b, edges[i0 + 1])
    seg_here, seg_next = cut - a, b - cut
    n = len(days)

    def per_day(weight: np.ndarray) -> np.ndarray:
        out = np.zeros(n + 1, dtype=np.int64)
        np.add.at(out, i0, weight * seg_here)
        np.add.at(out, i0 + 1, weight * seg_next)
        return out[:n]

    out = pd.DataFrame({name: per_day(np.asarray(w, dtype=np.int64)[:-1][keep])
                        for name, w in weights.items()},
                       index=pd.Index(days, name="date"))
    observed = per_day(np.ones(int(keep.sum()), dtype=np.int64))
    out["observed_s"] = observed
    out["day_s"] = np.diff(edges)
    out["coverage"] = observed / out["day_s"]
    out["snapshots"] = np.bincount(np.searchsorted(edges, t, side="right") - 1,
                                   minlength=n)[:n]
    return out


def daily(key: str, max_gap_s: int = MAX_GAP_S) -> pd.DataFrame:
    """Customer-minutes per local calendar day for one archive.

    One `cm_<series>` column per series in SERIES, the coverage columns from
    `integrate`, and `customers_served` (time-weighted over observed time) where
    the archive records it.
    """
    s = load_snapshots(key)
    weights = {}
    for name, terms in SERIES[key].items():
        w = np.zeros(len(s), dtype=np.int64)
        for term in terms:
            sign, col = (-1, term[1:]) if term.startswith("-") else (1, term)
            w += sign * s[col].to_numpy(np.int64)
        weights[f"cm_{name}"] = w
    if "customers_served" in s:
        weights["served_s"] = s["customers_served"].to_numpy(np.int64)
    out = integrate(s["t"].to_numpy(np.int64), weights,
                    ZoneInfo(UTILITIES[key]["tz"]), max_gap_s)
    for name in SERIES[key]:
        out[f"cm_{name}"] = out[f"cm_{name}"] / 60.0
    if "served_s" in out:
        obs = out["observed_s"].to_numpy()
        out["customers_served"] = np.where(obs > 0, out.pop("served_s")
                                           / np.maximum(obs, 1), np.nan)
    return out


def observed_days(key: str, series: str = "all", max_gap_s: int = MAX_GAP_S,
                  min_coverage: float = MIN_COVERAGE) -> pd.Series:
    """Daily customer-minutes on the days observed for at least min_coverage."""
    d = daily(key, max_gap_s)
    d = d[d["coverage"] >= min_coverage]
    return d[f"cm_{series}"]


# --- tail shape -------------------------------------------------------------

T_DF_GRID = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0,
             12.0, 15.0, 20.0, 30.0, 50.0, 100.0)
_EM_ITERATIONS = 400


def _t_fixed_df(x: np.ndarray, df: float) -> tuple[float, float, float]:
    """Student-t location and scale at fixed df, by EM with a fixed iteration
    count. Returns (log-likelihood, loc, scale)."""
    mu, s2 = float(np.median(x)), float(np.var(x))
    for _ in range(_EM_ITERATIONS):
        w = (df + 1.0) / (df + (x - mu) ** 2 / s2)
        mu = float(np.sum(w * x) / np.sum(w))
        s2 = float(np.sum(w * (x - mu) ** 2) / x.size)
    scale = float(np.sqrt(s2))
    return float(stats.t.logpdf(x, df, mu, scale).sum()), mu, scale


def tail_family(logs: np.ndarray) -> dict:
    """AIC of normal, Laplace and Student-t fitted to log daily values.

    Normal and Laplace by their closed-form maximum likelihood. Student-t by the
    profile over T_DF_GRID; the best grid df is reported, so it is a bracket,
    not a point estimate.
    """
    x = np.asarray(logs, dtype=float)
    mu, sd = float(x.mean()), float(x.std())
    ll_norm = float(stats.norm.logpdf(x, mu, sd).sum())
    loc = float(np.median(x))
    b = float(np.mean(np.abs(x - loc)))
    ll_lap = float(stats.laplace.logpdf(x, loc, b).sum())
    prof = [(_t_fixed_df(x, df)[0], df) for df in T_DF_GRID]
    ll_t, df_best = max(prof)
    aic = {"normal": 4.0 - 2.0 * ll_norm, "laplace": 4.0 - 2.0 * ll_lap,
           "student_t": 6.0 - 2.0 * ll_t}
    return {"aic": aic, "best": min(aic, key=aic.get), "student_t_df": df_best}


def hill_alpha(values: np.ndarray, top_share: float = 0.05) -> float:
    """Hill estimator of the upper tail index of the level, on the top k."""
    x = np.sort(np.asarray(values, dtype=float)[np.asarray(values) > 0])[::-1]
    k = max(int(len(x) * top_share), 10)
    if len(x) <= k:
        return float("nan")
    logs = np.log(x[:k]) - np.log(x[k])
    return float(1.0 / logs.mean()) if logs.mean() > 0 else float("nan")


def tail_shape(values: np.ndarray) -> dict:
    """The shape of a daily series on its positive days, as A14 reports it.

    Fitted on positive days, as IEEE 1366 does. The major-event-day rate is per
    observed day, zero days included, so a series with gaps is not credited with
    years it was not watched for.
    """
    v = np.asarray(values, dtype=float)
    pos = v[v > 0]
    logs = np.log(pos)
    mu, sd = logs.mean(), logs.std(ddof=1)
    exceed = int((logs > mu + BETA * sd).sum())
    sw = logs if len(logs) <= 5000 else np.random.default_rng(0).choice(
        logs, 5000, replace=False)
    # Three significant figures. At p-values this small the next digits differ
    # between scipy releases (by up to 1e-7 relative between 1.17 and 1.18),
    # which would break byte-identical results, and they carry no information.
    sw_p = float(f"{stats.shapiro(sw).pvalue:.3g}")
    return {
        "n_days": int(len(v)),
        "n_positive_days": int(len(pos)),
        "log_skewness": float(stats.skew(logs)),
        "log_excess_kurtosis": float(stats.kurtosis(logs)),
        "shapiro_wilk_p": sw_p,
        "tail_family": tail_family(logs),
        "hill_alpha_top_5pct": hill_alpha(pos),
        "med_days_at_2_5": exceed,
        "med_days_per_year_at_2_5": float(exceed * 365.25 / len(v)),
    }


# --- the exclusion, applied to a measured year --------------------------------

def retained_share_measured(year_values: np.ndarray, mu: float, sd: float,
                            betas) -> np.ndarray:
    """Share of a year's customer-minutes on days at or below exp(mu + beta*sd),
    for each beta: IEEE 1366's exclusion applied to the days themselves."""
    x = np.asarray(year_values, dtype=float)
    total = x.sum()
    logs = np.log(np.where(x > 0, x, np.nan))
    return np.array([x[~(logs > mu + b * sd)].sum() / total for b in betas])


def utility_years(values: pd.Series, min_days: int, min_prior_days: int) -> list[dict]:
    """Calendar years observed well enough to apply the standard to.

    A year qualifies with at least min_days observed days and at least
    min_prior_days observed days before it to fit the threshold on, as the
    standard fits on the preceding years. IEEE 1366 asks for five years of
    history; these archives allow at most a little over two, which A14 states.
    """
    idx = pd.to_datetime(pd.Index(values.index))
    out = []
    for year in sorted(set(idx.year)):
        start = pd.Timestamp(year=year, month=1, day=1)
        prior = values[(idx < start) & (idx >= start - pd.DateOffset(years=5))]
        this = values[idx.year == year]
        if len(this) >= min_days and len(prior) >= min_prior_days:
            p = np.log(prior[prior > 0].to_numpy(float))
            out.append({"year": int(year), "values": this.to_numpy(float),
                        "observed_days": int(len(this)),
                        "prior_days": int(len(prior)),
                        "mu": float(p.mean()), "sd": float(p.std(ddof=1))})
    return out
