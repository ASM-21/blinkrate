# The exclusion identity

Everything in track 3 rests on one result, so it is written out here rather than
left implicit in the code.

## Setup

IEEE 1366 defines a major event day as one whose daily SAIDI exceeds a threshold

$$T_{MED} = e^{\mu + \beta\sigma}$$

where $\mu$ and $\sigma$ are the mean and standard deviation of the natural logs
of daily SAIDI over a five-year history, and $\beta = 2.5$ in the published
standard. Days above $T_{MED}$ are removed from the reported "without major event
days" figure.

Let daily SAIDI $D_t$ be log-normal with parameters $\mu, \sigma$ — the
distribution the standard itself assumes when it fits logs and takes a
$\beta$-sigma point.

## The identity

Annual SAIDI with major event days is $\sum_t D_t$, with expectation
$365\,e^{\mu + \sigma^2/2}$.

Annual SAIDI without them is $\sum_t D_t \mathbb{1}\{D_t \le T\}$. The truncated
first moment of a log-normal is

$$\mathbb{E}\left[D\,\mathbb{1}\{D \le T\}\right]
= e^{\mu + \sigma^2/2}\,\Phi\!\left(\frac{\ln T - \mu - \sigma^2}{\sigma}\right).$$

Substituting $\ln T = \mu + \beta\sigma$, the argument collapses:

$$\frac{\ln T - \mu - \sigma^2}{\sigma}
= \frac{\beta\sigma - \sigma^2}{\sigma} = \beta - \sigma.$$

So the **retained share** — the fraction of annual outage minutes that survives
exclusion — is

$$r(\beta) = \frac{\mathbb{E}\left[\text{SAIDI without MED}\right]}
                  {\mathbb{E}\left[\text{SAIDI with MED}\right]}
          = \Phi(\beta - \sigma). \tag{1}$$

Three things drop out of (1) and all three matter.

**$\mu$ is gone.** The level of a utility's daily SAIDI does not affect what
share of it gets excluded. A utility with ten times the outage minutes excludes
the same proportion, given the same dispersion. Exclusion is a pure
dispersion story.

**Utility size is gone.** Nothing about customer count enters.

**One parameter is left.** Inverting (1) recovers it from the two numbers
EIA-861 actually publishes:

$$\hat\sigma = \beta - \Phi^{-1}(r_{\text{observed}}). \tag{2}$$

This is what makes a threshold sweep possible on data that contains no daily
series. Re-evaluating (1) at other $\beta$ gives the counterfactual reported
SAIDI.

## The sensitivity identity

Differentiating (1) with respect to $\beta$ and substituting
$\beta - \sigma = \Phi^{-1}(r)$ from (2):

$$\frac{dr}{d\beta} = \varphi(\beta - \sigma) = \varphi\!\left(\Phi^{-1}(r)\right). \tag{3}$$

Both $\beta$ and $\sigma$ vanish. **How sensitive a utility's reported SAIDI is
to the threshold parameter is a function of the exclusion share it already
reports, and of nothing else.** It is maximal at $r = 0.5$, where
$\varphi(0) = 0.3989$: a utility excluding half its outage minutes moves about
4% of its annual total across the line for every 0.1 change in $\beta$.

## Two admissibility bounds

At $\sigma = 0$, equation (1) gives $r = \Phi(2.5) = 0.99379$. A perfectly
uniform utility still excludes 0.6% of its minutes, because a continuous
distribution always puts some mass above a finite threshold. So **a reported
retained share above 0.99379 is outside the model** — most sharply, a reported
$r$ of exactly 1.

At the other end the model runs out of room too, though the bound is set by the
finite-sample calibration rather than by (1): with 365 days, the median year
contains no day above a $\beta = 2.5$ threshold once $\sigma$ is large enough
that the annual total is a single day.

## Why the code does not use (1) directly

Equation (1) is a ratio of expectations. A filed utility-year is one realization
of 365 days, and its reported retained share is a ratio of realized sums. For
heavy-tailed daily SAIDI those differ substantially — at $\sigma = 2.5$ the
closed form says 0.500 while simulating the 1366 procedure on 365-day years
gives a median of 0.610.

So `reliability_metrics.retained_share_closed_form` is the analytic anchor and
the tracks invert `finite_sample`, a simulated median-realization surface. Track
7 measures the gap between them: max absolute error 0.196 for the closed form
against simulation, 0.019 for the calibrated surface.

## What this inherits

Log-normality. It is IEEE 1366's assumption, not an extra one this repo adds,
but a model-implied sensitivity is not a measurement and the distinction is not
cosmetic. Attack A1 in track 8 re-runs the whole thing with heavier-tailed daily
SAIDI to see how much of the result is the assumption.
