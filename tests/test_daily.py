"""The daily outage data and the code that turns it into attack A14.

The vendored snapshots are pinned to their documented build, the integration
into daily customer-minutes is checked on records whose answer is known in
advance, and the tail fits are checked against the general-purpose optimizer
they replace.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from scipy import stats

from blinkrate.shared import daily

ROOT = Path(__file__).resolve().parents[1]
LA = ZoneInfo("America/Los_Angeles")


def _ts(text: str, tz: ZoneInfo = LA) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=tz).timestamp())


# --- the vendored data is the documented data ---------------------------------

def test_vendored_snapshots_match_the_checksums_their_readme_publishes():
    """data/daily/README.md states the checksums a rebuild from the pinned
    archive commits reproduces. If the files and the README disagree, one of
    them is wrong about where the numbers came from."""
    readme = (ROOT / "data" / "daily" / "README.md").read_text()
    for key, u in daily.UTILITIES.items():
        digest = hashlib.sha256((daily.DATA / u["file"]).read_bytes()).hexdigest()
        assert re.search(rf"{digest}\s+{re.escape(u['file'])}", readme), key
        assert u["commit"] in readme


def test_snapshot_series_are_ordered_and_complete():
    pge, fpl = daily.load_snapshots("pge"), daily.load_snapshots("fpl")
    assert len(pge) == 66011 and len(fpl) == 89310
    for s in (pge, fpl):
        assert (np.diff(s["t"].to_numpy()) > 0).all()
        assert (s["customers_out"] >= 0).all()
    # the parts PG&E's map attributes to shutoffs and planned work are parts
    assert (pge["psps"] + pge["planned"] <= pge["customers_out"]).all()
    # the same 35 FPL counties throughout, about 5.1 to 5.3 million customers
    assert fpl["customers_served"].between(5.0e6, 5.4e6).all()


def test_known_events_land_on_the_right_local_days():
    """The largest day in each series is a documented event, which pins the
    time zones and, for PG&E, the cause classification."""
    pge = daily.daily("pge")
    worst = pge["cm_all"].idxmax()
    assert str(worst) == "2019-10-27"
    # that day was a Public Safety Power Shutoff, so nearly all of it is PSPS
    assert pge.loc[worst, "cm_excl_psps"] < 0.1 * pge.loc[worst, "cm_all"]
    fpl = daily.daily("fpl")
    assert str(fpl["cm_all"].idxmax()) == "2022-09-29"  # Hurricane Ian


# --- integration, on records with known answers -----------------------------

def test_integration_is_exact_for_a_constant_outage():
    """60 customers out all day for two days, snapshots every ten minutes."""
    t0 = _ts("2021-06-01T00:00:00")
    t = np.arange(t0, t0 + 2 * 86400 + 1, 600)
    d = daily.integrate(t, {"cm": np.full(len(t), 60)}, LA)
    assert list(d["coverage"].iloc[:2]) == [1.0, 1.0]
    assert list(d["cm"].iloc[:2] / 60) == [60 * 1440, 60 * 1440]


def test_integration_splits_an_interval_at_local_midnight():
    t = np.array([_ts("2021-06-01T23:30:00"), _ts("2021-06-02T00:30:00")])
    d = daily.integrate(t, {"cm": np.array([10, 0])}, LA)
    assert list(d["cm"] / 60) == [300, 300]   # 30 minutes on each side


def test_a_long_silence_is_unobserved_rather_than_quiet():
    t = np.array([_ts("2021-06-01T00:00:00"), _ts("2021-06-01T04:00:00"),
                  _ts("2021-06-01T04:10:00")])
    d = daily.integrate(t, {"cm": np.array([100, 5, 5])}, LA)
    # the 4-hour silence exceeds the 3-hour rule and contributes nothing; only
    # the last ten minutes, at 5 customers, are counted
    assert d["cm"].iloc[0] / 60 == 5 * 10
    assert d["observed_s"].iloc[0] == 600


def test_daylight_saving_days_have_their_real_length():
    """Local days are 23 and 25 hours at the changes. A day treated as 24 hours
    would misstate coverage by about 4% twice a year."""
    t0 = _ts("2021-03-13T00:00:00")
    t = np.arange(t0, _ts("2021-03-16T00:00:00") + 1, 600)
    d = daily.integrate(t, {"cm": np.ones(len(t), dtype=int)}, LA)
    assert d.loc[datetime(2021, 3, 14).date(), "day_s"] == 23 * 3600
    assert (d["coverage"].iloc[:3] == 1.0).all()
    t0 = _ts("2021-11-06T00:00:00")
    t = np.arange(t0, _ts("2021-11-09T00:00:00") + 1, 600)
    d = daily.integrate(t, {"cm": np.ones(len(t), dtype=int)}, LA)
    assert d.loc[datetime(2021, 11, 7).date(), "day_s"] == 25 * 3600


# --- the tail fits --------------------------------------------------------

def test_em_matches_scipy_at_fixed_degrees_of_freedom():
    """With df fixed the likelihood in location and scale is well behaved, so
    EM and scipy's optimizer must agree; this checks the EM itself."""
    rng = np.random.default_rng(3)
    x = 2.0 + 0.7 * rng.standard_t(4, 2000)
    ll_em, loc, scale = daily._t_fixed_df(x, 4.0)
    _, loc_s, scale_s = stats.t.fit(x, fdf=4.0)
    assert loc == pytest.approx(loc_s, abs=1e-3)
    assert scale == pytest.approx(scale_s, rel=1e-3)
    assert ll_em >= stats.t.logpdf(x, 4.0, loc_s, scale_s).sum() - 1e-6


def test_profile_is_never_worse_than_scipys_general_optimizer():
    """The reason the profile exists: on PG&E's daily data scipy's joint fit
    (1.15 to 1.18) stops at a local optimum nearly 100 log-likelihood units
    below the profile's best, enough to flip which tail family wins. Only "never
    worse" is asserted, so a better optimizer in a later scipy cannot fail it."""
    for key in ("pge", "fpl"):
        v = daily.observed_days(key).to_numpy(float)
        logs = np.log(v[v > 0])
        df_s, loc_s, scale_s = stats.t.fit(logs)
        ll_scipy = stats.t.logpdf(logs, df_s, loc_s, scale_s).sum()
        ll_profile = (6.0 - daily.tail_family(logs)["aic"]["student_t"]) / 2.0
        assert ll_profile >= ll_scipy - 0.5, key
