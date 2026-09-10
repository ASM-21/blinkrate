"""Finite-sample calibration of the retained-share map.

The closed form r = Phi(beta - sigma) is a ratio of expectations. A utility-year
is one realization of 365 days, and its reported retained share is a ratio of
realized sums. Those are not the same thing, and for heavy-tailed daily SAIDI
they are not close: at sigma = 2.5 the closed form says half the annual minutes
survive exclusion, while simulating the 1366 procedure on 365-day years says
about 62% do. Jensen plus a 365-day sample where the annual total is dominated
by a handful of days.

So the closed form is the analytic anchor and this module is what the tracks
actually invert. It simulates the procedure IEEE 1366 specifies (five-year
fitting window, zero-SAIDI days dropped, threshold exp(mu_hat + beta*sigma_hat))
across a grid of sigma, and stores the MEDIAN realized retained share.
Inversion and the sensitivity curve are then interpolations on that surface.

Median, not mean, and the choice is load-bearing. At large sigma the annual
total is one day, and in the minority of draws where that day happens to land
below the threshold the realized r jumps to nearly 1. Those draws drag the mean
up to an asymptote near 0.10 while the median falls smoothly to 0. Inverting on
the mean makes every heavily-excluding utility-year look un-modelable; inverting
on the median matches the typical realization, which is what a single reported
utility-year is. A regression test pins this.

The calibration grid is cached to data/calibration_med.npz. Rebuild with
`python -m blinkrate.shared.finite_sample`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .reliability_metrics import BETA_STANDARD, fit_lognormal

CACHE = Path(__file__).resolve().parents[2] / "data" / "calibration_med.npz"

SIGMA_GRID = np.round(np.arange(0.05, 8.001, 0.05), 4)
BETA_GRID = np.round(np.arange(1.0, 5.001, 0.05), 4)
N_SIMS = 1500
DAYS = 365
FIT_YEARS = 5
SEED = 20260907


def _simulate_one_sigma(sigma: float, rng: np.random.Generator,
                        n_sims: int = N_SIMS) -> np.ndarray:
    """Median realized retained share at every beta in BETA_GRID, for this sigma."""
    draws = np.empty((n_sims, BETA_GRID.size))
    mu = 0.0  # r is invariant to mu; the level cancels in the ratio.
    for i in range(n_sims):
        window = rng.lognormal(mu, sigma, DAYS * FIT_YEARS)
        year = window[:DAYS]
        mu_hat, sigma_hat = fit_lognormal(window)
        thresholds = np.exp(mu_hat + BETA_GRID * sigma_hat)
        year_sorted = np.sort(year)
        cum = np.concatenate([[0.0], np.cumsum(year_sorted)])
        # minutes on days at or below each threshold
        idx = np.searchsorted(year_sorted, thresholds, side="right")
        draws[i] = cum[idx] / cum[-1]
    return np.median(draws, axis=0)


def _enforce_monotone(surface: np.ndarray) -> np.ndarray:
    """Project each beta column onto the non-increasing-in-sigma cone.

    r is decreasing in sigma by construction: more dispersed daily SAIDI puts
    more of the annual total above any fixed quantile threshold. Monte Carlo
    noise in the median breaks that at the 0.01-0.04 level, which is small in
    absolute terms but makes the inversion (an interpolation on r) non-monotone
    and costs about 0.01 of round-trip accuracy. A running minimum along
    increasing sigma removes only upward noise and never invents structure.
    """
    return np.minimum.accumulate(surface, axis=0)


def build_calibration(n_sims: int = N_SIMS, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    surface = np.vstack([_simulate_one_sigma(s, rng, n_sims) for s in SIGMA_GRID])
    surface = _enforce_monotone(surface)
    return {"sigma_grid": SIGMA_GRID, "beta_grid": BETA_GRID, "surface": surface,
            "n_sims": np.array([n_sims]), "seed": np.array([seed])}


_CACHED: dict | None = None


def calibration() -> dict:
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    if CACHE.exists():
        with np.load(CACHE) as z:
            _CACHED = {k: z[k] for k in z.files}
    else:
        _CACHED = build_calibration()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(CACHE, **_CACHED)
    return _CACHED


def _column_at_beta(beta: float) -> np.ndarray:
    c = calibration()
    return np.array([np.interp(beta, c["beta_grid"], row) for row in c["surface"]])


def implied_sigma_fs(retained_share: np.ndarray | float,
                     beta: float = BETA_STANDARD) -> np.ndarray:
    """Invert the calibrated map: sigma such that median(r | sigma, beta) = r_observed.

    NaN where the observed retained share is above what the model can produce at
    sigma -> 0 (a year too clean for the log-normal) or below what it produces at
    the top of the sigma grid.
    """
    c = calibration()
    r_of_sigma = _column_at_beta(beta)
    # r is monotone decreasing in sigma; flip for np.interp.
    order = np.argsort(r_of_sigma)
    xs, ys = r_of_sigma[order], c["sigma_grid"][order]
    r = np.asarray(retained_share, dtype=float)
    out = np.interp(r, xs, ys, left=np.nan, right=np.nan)
    return np.where((r >= xs.min()) & (r <= xs.max()), out, np.nan)


def retained_share_fs(sigma: np.ndarray | float,
                      beta: np.ndarray | float = BETA_STANDARD) -> np.ndarray:
    """Calibrated r(sigma, beta), bilinear on the cached surface."""
    c = calibration()
    sig = np.atleast_1d(np.asarray(sigma, dtype=float))
    bet = np.atleast_1d(np.asarray(beta, dtype=float))
    # interpolate along beta for each grid sigma, then along sigma
    cols = np.vstack([np.interp(bet, c["beta_grid"], row) for row in c["surface"]])
    out = np.empty((sig.size, bet.size))
    for j in range(bet.size):
        out[:, j] = np.interp(sig, c["sigma_grid"], cols[:, j],
                              left=np.nan, right=np.nan)
    return out


def sensitivity_curve_fs(retained_share_observed: np.ndarray,
                         betas: np.ndarray,
                         beta_reported: float = BETA_STANDARD) -> np.ndarray:
    """Retained share at each beta for utility-years reporting `r` at beta_reported.

    Shape (n_rows, n_betas). NaN rows are utility-years outside the model.
    """
    sigma = implied_sigma_fs(retained_share_observed, beta=beta_reported)
    out = np.full((np.asarray(sigma).size, np.asarray(betas).size), np.nan)
    ok = np.isfinite(sigma)
    if ok.any():
        out[ok] = retained_share_fs(np.asarray(sigma)[ok], betas)
    return out


if __name__ == "__main__":  # pragma: no cover
    cal = build_calibration()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, **cal)
    print(f"wrote {CACHE} surface={cal['surface'].shape}")
