"""Tests that pin the shared layer's behaviour and the traps it exists to avoid."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from blinkrate.shared import finite_sample as fs
from blinkrate.shared import ingest
from blinkrate.shared import reliability_metrics as rm


# --------------------------------------------------------------------------
# ingest: the layout traps
# --------------------------------------------------------------------------

def test_all_four_years_load():
    p = ingest.load_panel()
    assert set(p["year"].dropna().unique()) == {2013, 2014, 2015, 2022}


def test_panel_row_count_stable():
    assert len(ingest.load_panel()) == 3854


def test_analysis_sample_row_count_stable():
    assert len(ingest.analysis_sample()) == 3427


def test_both_reporting_standards_survive_the_read():
    """The IEEE and Other blocks share column names in the source file.

    A header-based read keeps one and silently drops the other. This asserts
    both are present in usable numbers; if it fails, `_standardize` is reading
    by name somewhere it should be reading by position.
    """
    s = ingest.analysis_sample()
    counts = s["standard"].value_counts()
    assert counts["IEEE"] > 2000
    assert counts["Other"] > 900


def test_missing_values_are_not_read_as_zero():
    """EIA writes missing as '.' and thousands with commas.

    Tested on the raw per-year read, not the panel: `_standardize` picks
    whichever of the two reporting blocks is populated, so by then the NaNs are
    gone by design. A '.' silently coerced to 0 would invent perfect
    reliability, and a comma-formatted customer count coerced to NaN would drop
    every large utility.
    """
    raw = ingest.load_year(2015)
    assert raw["ieee_saidi_with"].isna().sum() > 0, "'.' was coerced, not parsed"
    assert raw["other_saidi_with"].isna().sum() > 0
    assert (raw["ieee_saidi_with"].dropna() == 0).mean() < 0.02
    assert ingest.load_panel()["customers"].max() > 1e6, "comma counts truncated"


def test_ownership_joined_for_pre_2022_years():
    """Pre-2022 reliability files carry no ownership column; it is joined from
    the Sales file. If the join breaks, everything is 'Other'."""
    s = ingest.analysis_sample()
    early = s[s["year"] < 2022]
    assert (early["ownership_class"] == "Other").mean() < 0.05
    assert set(early["ownership_class"].unique()) >= {"IOU", "Coop", "Municipal"}


def test_retained_share_bounded_and_consistent():
    s = ingest.analysis_sample()
    assert s["retained_share"].between(0, 1).all()
    recomputed = s["saidi_without"] / s["saidi_with"]
    assert np.allclose(recomputed, s["retained_share"])
    assert np.allclose(s["excluded_minutes"], s["saidi_with"] - s["saidi_without"])


def test_rejected_rows_are_accounted_for():
    kept = len(ingest.analysis_sample())
    rejected = len(ingest.rejected_rows())
    assert kept + rejected == len(ingest.load_panel())


# --------------------------------------------------------------------------
# the exclusion identity
# --------------------------------------------------------------------------

def test_closed_form_matches_hand_derivation():
    """r = Phi(beta - sigma), independent of mu."""
    for sigma in (0.5, 1.0, 2.0):
        assert rm.retained_share_closed_form(sigma) == pytest.approx(
            stats.norm.cdf(2.5 - sigma))


def test_closed_form_inversion_round_trips():
    for r in (0.9, 0.75, 0.5, 0.3):
        sigma = rm.implied_sigma(np.array([r]))
        assert rm.retained_share_closed_form(sigma)[0] == pytest.approx(r, abs=1e-9)


def test_zero_exclusion_is_outside_the_lognormal_model():
    """Phi(2.5) = 0.99379 is the cleanest year a log-normal can produce at
    beta = 2.5. A reported retained share of exactly 1 is not representable,
    and that is track 3's first finding rather than a bug to clip away."""
    assert rm.R_MAX_ADMISSIBLE == pytest.approx(0.99379, abs=1e-5)
    assert np.isnan(rm.implied_sigma(np.array([1.0]))[0])
    assert np.isnan(rm.implied_sigma(np.array([0.995]))[0])
    assert np.isfinite(rm.implied_sigma(np.array([0.99]))[0])


def test_sensitivity_identity_depends_only_on_r():
    """dr/dbeta = phi(Phi^-1(r)): beta and sigma both cancel."""
    r = np.array([0.3, 0.5, 0.7])
    d = rm.d_retained_d_beta(r)
    assert d.max() == pytest.approx(stats.norm.pdf(0.0), abs=1e-12)
    assert rm.d_retained_d_beta(np.array([0.5]))[0] == pytest.approx(0.3989422804)
    # same r evaluated at a different nominal beta gives the same derivative
    assert np.allclose(d, rm.d_retained_d_beta(r, beta=3.0))


def test_procedural_engine_matches_closed_form_at_low_sigma():
    rng = np.random.default_rng(0)
    sigma = 0.8
    vals = []
    for _ in range(200):
        w = rng.lognormal(0.0, sigma, rm.DAYS_PER_YEAR * 5)
        vals.append(rm.simulate_med_exclusion(w[:rm.DAYS_PER_YEAR], w).retained_share)
    assert np.median(vals) == pytest.approx(
        float(rm.retained_share_closed_form(sigma)), abs=0.02)


def test_beta_is_actually_tunable():
    """A lower beta must exclude more. If the parameter is being ignored
    somewhere, this catches it."""
    rng = np.random.default_rng(1)
    w = rng.lognormal(0.0, 2.0, rm.DAYS_PER_YEAR * 5)
    year = w[:rm.DAYS_PER_YEAR]
    tight = rm.simulate_med_exclusion(year, w, beta=1.5)
    loose = rm.simulate_med_exclusion(year, w, beta=3.5)
    assert tight.retained_share < loose.retained_share
    assert tight.n_med_days > loose.n_med_days
    assert tight.t_med < loose.t_med


def test_zero_days_dropped_from_fit_changes_the_threshold():
    """IEEE 1366 drops zero-SAIDI days from the log-normal fit. Keeping them
    (via a clip) is a different threshold, and the flag must actually do
    something."""
    daily = np.concatenate([np.zeros(200), np.full(165, 10.0)])
    with_drop = rm.med_threshold(daily, drop_zero_days=True)
    without = rm.med_threshold(daily, drop_zero_days=False)
    assert with_drop != pytest.approx(without)


# --------------------------------------------------------------------------
# finite-sample calibration
# --------------------------------------------------------------------------

def test_calibration_surface_shape_and_monotonicity():
    c = fs.calibration()
    assert c["surface"].shape == (c["sigma_grid"].size, c["beta_grid"].size)
    j = int(np.argmin(np.abs(c["beta_grid"] - 2.5)))
    col = c["surface"][:, j]
    # retained share falls as daily dispersion rises
    assert np.all(np.diff(col) <= 1e-9)


def test_calibration_is_median_not_mean():
    """Load-bearing design call. At large sigma the mean realized retained share
    asymptotes near 0.10 because a minority of years contain no qualifying day,
    while the median falls to 0. Inverting on the mean would declare most
    heavily-excluding utility-years un-modelable. This pins the median."""
    rng = np.random.default_rng(5)
    sigma = 4.0
    vals = []
    for _ in range(300):
        w = rng.lognormal(0.0, sigma, rm.DAYS_PER_YEAR * 5)
        vals.append(rm.simulate_med_exclusion(w[:rm.DAYS_PER_YEAR], w).retained_share)
    vals = np.array(vals)
    assert vals.mean() - np.median(vals) > 0.05, "mean and median must diverge here"
    surface = float(fs.retained_share_fs(sigma).ravel()[0])
    assert surface == pytest.approx(float(np.median(vals)), abs=0.05)
    assert surface < vals.mean()


def test_calibration_beats_closed_form_at_high_sigma():
    rng = np.random.default_rng(7)
    sigma = 2.5
    vals = [rm.simulate_med_exclusion(
        (w := rng.lognormal(0.0, sigma, rm.DAYS_PER_YEAR * 5))[:rm.DAYS_PER_YEAR],
        w).retained_share for _ in range(300)]
    truth = float(np.median(vals))
    err_cf = abs(float(rm.retained_share_closed_form(sigma)) - truth)
    err_cal = abs(float(fs.retained_share_fs(sigma).ravel()[0]) - truth)
    assert err_cal < err_cf / 3


def test_finite_sample_inversion_round_trips():
    for r in (0.95, 0.8, 0.6, 0.4):
        sigma = fs.implied_sigma_fs(np.array([r]))
        assert np.isfinite(sigma[0])
        back = float(fs.retained_share_fs(sigma[0]).ravel()[0])
        assert back == pytest.approx(r, abs=0.01)


def test_exclusion_switches_off_above_beta_2_95():
    """The mechanism has a cliff just above the standard's value: with 365 days,
    the median year contains no day past a 3-sigma threshold."""
    c = fs.calibration()
    j3 = int(np.argmin(np.abs(c["beta_grid"] - 3.0)))
    assert np.all(c["surface"][:, j3] >= 0.999999)
    j29 = int(np.argmin(np.abs(c["beta_grid"] - 2.9)))
    assert c["surface"][:, j29].min() < 0.5


def test_calibration_is_seeded_and_reproducible():
    """The committed surface must be regenerable bit for bit.

    A cached artifact nobody can reproduce is a magic number. Checked on a small
    grid slice rather than the full build so the test stays cheap; the full
    rebuild is exercised by verify.sh.
    """
    a = fs.build_calibration(n_sims=25, seed=99)
    b = fs.build_calibration(n_sims=25, seed=99)
    assert np.array_equal(a["surface"], b["surface"])

    c = fs.calibration()
    assert int(c["seed"][0]) == fs.SEED
    assert int(c["n_sims"][0]) == fs.N_SIMS


def test_committed_calibration_matches_its_own_parameters():
    """Guards against a cache built with different settings being committed."""
    c = fs.calibration()
    assert np.array_equal(c["sigma_grid"], fs.SIGMA_GRID)
    assert np.array_equal(c["beta_grid"], fs.BETA_GRID)
