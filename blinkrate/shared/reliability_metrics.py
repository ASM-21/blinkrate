"""IEEE 1366 major-event-day exclusion, with the threshold as a tunable parameter.

Two implementations of the same object, kept side by side on purpose:

`simulate_med_exclusion` is procedural. It takes a daily SAIDI series, fits the
log-normal the way IEEE 1366 tells you to (natural logs of daily SAIDI over a
five-year window, zero-SAIDI days dropped from the fit), forms
T_MED = exp(mu_hat + beta * sigma_hat), and drops the days above it. This is
what a utility actually does.

`retained_share_closed_form` is analytic. If daily SAIDI is log-normal(mu, sigma)
then the share of annual outage minutes that survives exclusion is

    r(beta) = Phi(beta - sigma)                                            (1)

which depends on the dispersion of daily SAIDI and on beta, and on nothing else.
Not on mu, not on the level of SAIDI, not on utility size. The derivation is in
docs/derivation.md; it is the standard truncated-lognormal first moment
E[D | D <= T] with ln T - mu = beta * sigma substituted in.

Equation (1) is what makes this repo possible. EIA-861 publishes annual SAIDI
with and without major event days but not the daily series, so nothing can be
recomputed directly. Inverting (1) recovers the one latent parameter that
governs exclusion from the two numbers that are published:

    sigma_hat = beta - Phi^-1(r_observed)                                   (2)

and then re-evaluating (1) at other beta gives the sensitivity curve.

This is a MODEL-IMPLIED sensitivity, not a measurement. It inherits IEEE 1366's
own log-normality assumption. Track 7 checks the closed form against the
procedural simulator; track 8 attacks the log-normal assumption itself with
heavier-tailed daily distributions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

BETA_STANDARD = 2.5  # IEEE 1366-2012 "2.5 beta method"
DAYS_PER_YEAR = 365

# Above this retained share the closed form implies sigma <= 0: the log-normal
# model cannot produce a year that clean. Phi(2.5) = 0.99379...
R_MAX_ADMISSIBLE = float(stats.norm.cdf(BETA_STANDARD))


@dataclass(frozen=True)
class MEDResult:
    """Outcome of applying a threshold to one utility-year of daily SAIDI."""

    beta: float
    t_med: float
    saidi_with: float
    saidi_without: float
    n_med_days: int
    mu_hat: float
    sigma_hat: float

    @property
    def retained_share(self) -> float:
        return self.saidi_without / self.saidi_with if self.saidi_with > 0 else np.nan

    @property
    def excluded_share(self) -> float:
        return 1.0 - self.retained_share


def fit_lognormal(daily_saidi: np.ndarray, drop_zero_days: bool = True
                  ) -> tuple[float, float]:
    """Fit the log-normal IEEE 1366 uses for T_MED.

    1366 fits on the natural logs of daily SAIDI across a five-year window and
    excludes days with zero SAIDI from the fit, because ln(0) is undefined and
    a utility with many clean days would otherwise get an absurd threshold.
    `drop_zero_days=False` exists so track 8 can test how much that convention
    is doing.
    """
    d = np.asarray(daily_saidi, dtype=float)
    d = d[np.isfinite(d)]
    if drop_zero_days:
        d = d[d > 0]
    else:
        d = np.clip(d, 1e-9, None)
    if d.size < 2:
        return np.nan, np.nan
    logs = np.log(d)
    # 1366 specifies the sample standard deviation (ddof=1).
    return float(logs.mean()), float(logs.std(ddof=1))


def med_threshold(daily_saidi: np.ndarray, beta: float = BETA_STANDARD,
                  drop_zero_days: bool = True) -> float:
    mu, sigma = fit_lognormal(daily_saidi, drop_zero_days=drop_zero_days)
    if not np.isfinite(mu):
        return np.inf
    return float(np.exp(mu + beta * sigma))


def simulate_med_exclusion(daily_saidi_year: np.ndarray,
                           daily_saidi_fit_window: np.ndarray | None = None,
                           beta: float = BETA_STANDARD,
                           drop_zero_days: bool = True) -> MEDResult:
    """Apply the 2.5-beta method procedurally to one year of daily SAIDI.

    `daily_saidi_fit_window` is the five-year history the threshold is fitted on.
    Defaults to the year itself, which is what you do when you have one year of
    data and is a source of bias track 7 quantifies.
    """
    year = np.asarray(daily_saidi_year, dtype=float)
    window = year if daily_saidi_fit_window is None else np.asarray(
        daily_saidi_fit_window, dtype=float)
    mu, sigma = fit_lognormal(window, drop_zero_days=drop_zero_days)
    t_med = np.exp(mu + beta * sigma) if np.isfinite(mu) else np.inf
    kept = year[year <= t_med]
    return MEDResult(
        beta=float(beta), t_med=float(t_med),
        saidi_with=float(year.sum()), saidi_without=float(kept.sum()),
        n_med_days=int((year > t_med).sum()),
        mu_hat=float(mu), sigma_hat=float(sigma),
    )


def retained_share_closed_form(sigma: np.ndarray | float,
                               beta: float = BETA_STANDARD) -> np.ndarray:
    """r(beta) = Phi(beta - sigma). Equation (1)."""
    return stats.norm.cdf(np.asarray(beta, dtype=float) - np.asarray(sigma, dtype=float))


def implied_sigma(retained_share: np.ndarray | float,
                  beta: float = BETA_STANDARD) -> np.ndarray:
    """sigma_hat = beta - Phi^-1(r). Equation (2).

    Returns NaN where r >= Phi(beta), i.e. where the reported exclusion is
    smaller than the log-normal model can produce at any non-negative sigma.
    Those utility-years are not a nuisance to be clipped away: they are 30% of
    the sample and track 3's first finding.
    """
    r = np.asarray(retained_share, dtype=float)
    out = np.full(r.shape, np.nan) if r.ndim else np.nan
    admissible = (r > 0) & (r < stats.norm.cdf(beta))
    sigma = beta - stats.norm.ppf(np.clip(r, 1e-12, 1 - 1e-12))
    return np.where(admissible, sigma, np.nan)


def sensitivity_curve(retained_share_observed: np.ndarray | float,
                      betas: np.ndarray,
                      beta_reported: float = BETA_STANDARD) -> np.ndarray:
    """Retained share at each beta, for a utility-year reporting `r` at 2.5.

    Shape (n_utility_years, n_betas).
    """
    sigma = implied_sigma(retained_share_observed, beta=beta_reported)
    sigma = np.atleast_1d(sigma)[:, None]
    return retained_share_closed_form(sigma, beta=np.asarray(betas)[None, :])


def d_retained_d_beta(retained_share: np.ndarray | float,
                      beta: float = BETA_STANDARD) -> np.ndarray:
    """dr/dbeta = phi(Phi^-1(r)).

    Note what drops out: beta and sigma both vanish, so the threshold-sensitivity
    of a utility's reported SAIDI is a pure function of the exclusion share it
    already reports. Maximal at r = 0.5 (phi(0) = 0.3989), where a 0.1 move in
    beta shifts about 4% of the utility's annual outage minutes across the line.
    """
    r = np.asarray(retained_share, dtype=float)
    r = np.clip(r, 1e-12, 1 - 1e-12)
    return stats.norm.pdf(stats.norm.ppf(r))


def saidi_at_beta(saidi_with: np.ndarray, retained_share_observed: np.ndarray,
                  betas: np.ndarray, beta_reported: float = BETA_STANDARD
                  ) -> np.ndarray:
    """Reported SAIDI-without-MED that each utility-year would have published
    had the standard specified a different beta. Shape (n_rows, n_betas)."""
    curve = sensitivity_curve(retained_share_observed, betas, beta_reported)
    return np.asarray(saidi_with, dtype=float)[:, None] * curve
