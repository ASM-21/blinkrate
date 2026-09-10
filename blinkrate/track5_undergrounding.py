"""Track 5 - what outage burden does undergrounding have to avoid to pay back?

A payback model, not a measurement. Every parameter is a published figure with
its source recorded in PARAMS below, and the point of the track is what happens
to the answer across the published RANGE rather than at any single point
estimate.

The interesting thing is not the breakeven number. It is that the two
literatures on undergrounding's reliability benefit disagree by an order of
magnitude, and which one you pick decides the answer:

  - engineering case studies of converted circuits report SAIDI reductions of
    73% (FPL, 5-year average on converted laterals) to 99.6% (Virginia Electric
    and Power, 2025 program report), but these are selected circuits, chosen for
    conversion because they performed badly, and measured after conversion;
  - the one utility-level econometric estimate in the same literature (Larsen
    et al. 2020, as summarised in the 2023 New York undergrounding study) finds
    a percentage point of underground share buys about 0.426% lower SAIFI, and
    reports the SAIDI relationship as negative but statistically insignificant.

So this track reports the breakeven twice and lets the gap be the finding.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .shared import ingest
from .shared.io import PALETTE, save_figure, save_results, style_axes

PARAMS = {
    "cost_per_mile_usd": {
        "low": 600_000, "central": 3_800_000, "high": 13_000_000,
        "source": ("EEI 'Out of Sight, Out of Mind' conversion range restated in "
                   "2019 USD ($0.6M-$13M/mile); central value is the CPUC "
                   "average conversion cost of $3.8M per circuit mile across the "
                   "three California IOUs"),
    },
    "asset_life_years": {"value": 30,
                         "source": "underground plant life commonly cited at ~30 "
                                   "years vs 40-50 for overhead"},
    "discount_rate": {"low": 0.05, "central": 0.07, "high": 0.09,
                      "source": "utility WACC range used for illustration"},
    "cost_per_customer_hour_usd": {
        "low": 150, "central": 370.2, "high": 800,
        "source": ("$370.2 (2022 USD) average cost per customer-hour of "
                   "interruption used in Quantifying distribution system "
                   "resilience from utility data (arXiv:2407.10773), derived "
                   "from the LBNL ICE Calculator customer mix; low/high bracket "
                   "the residential-heavy and commercial-heavy ends"),
    },
    "saidi_reduction": {
        "econometric": 0.10,
        "case_study_low": 0.73,
        "case_study_high": 0.996,
        "source": ("case studies: FPL 73% five-year average, WPSC SMRP 95%, "
                   "Virginia Electric and Power 99.6%. Econometric: Larsen et "
                   "al. 2020 finds SAIDI effect negative and statistically "
                   "insignificant; 0.10 is used here as a deliberately generous "
                   "stand-in for 'small and not clearly distinguishable from "
                   "zero', so the econometric case is not strawmanned"),
    },
    "us_distribution_line_miles": {
        "value": 5_500_000,
        "source": "5.5 million miles of US distribution line, EEI figure as "
                  "restated by Exponent",
    },
}


def customers_per_mile() -> dict:
    """Derived from this repo's own data rather than assumed.

    Total US retail customers come from EIA-861 Sales to Ultimate Customers
    2022; line miles are the national EEI figure. The result is a national
    average and hides an enormous urban/rural spread, which is why the sweep
    below runs across densities instead of using one number.
    """
    s = pd.read_excel(ingest.DATA_DIR / "Sales_Ult_Cust_2022.xlsx", sheet_name=0,
                      header=None, skiprows=3, dtype=str)
    part = s.iloc[:, 3].astype(str).str.strip()
    cust = sum(ingest._to_num(s.loc[part.isin(["A", "B", "C"]), c]).fillna(0)
               for c in (11, 14, 17, 20))
    total = float(cust.sum())
    miles = PARAMS["us_distribution_line_miles"]["value"]
    return {
        "total_us_customers_2022": total,
        "line_miles": miles,
        "national_customers_per_mile": total / miles,
    }


def annualize(capital: float, rate: float, life: int) -> float:
    """Capital recovery factor."""
    return capital * (rate * (1 + rate) ** life) / ((1 + rate) ** life - 1)


def breakeven_saidi(cost_per_mile: float, customers_per_mile_val: float,
                    cost_per_customer_hour: float, reduction: float,
                    rate: float, life: int) -> float:
    """Baseline SAIDI (minutes/yr) at which undergrounding a mile breaks even.

    annualized cost per mile == customers/mile * SAIDI_hours * reduction * $/cust-hr
    """
    annual = annualize(cost_per_mile, rate, life)
    denom = customers_per_mile_val * reduction * cost_per_customer_hour
    return np.inf if denom <= 0 else (annual / denom) * 60.0


def sweep(cpm_val: float) -> dict:
    rows = {}
    life = PARAMS["asset_life_years"]["value"]
    for red_name, red in (("econometric", PARAMS["saidi_reduction"]["econometric"]),
                          ("case_study_low", PARAMS["saidi_reduction"]["case_study_low"]),
                          ("case_study_high", PARAMS["saidi_reduction"]["case_study_high"])):
        for cost_name in ("low", "central", "high"):
            for voll_name in ("low", "central", "high"):
                key = f"{red_name}|cost_{cost_name}|voll_{voll_name}"
                rows[key] = breakeven_saidi(
                    PARAMS["cost_per_mile_usd"][cost_name], cpm_val,
                    PARAMS["cost_per_customer_hour_usd"][voll_name], red,
                    PARAMS["discount_rate"]["central"], life)
    return rows


def against_observed(breakevens: dict) -> dict:
    """How many real utility-years actually clear each breakeven?"""
    df = ingest.analysis_sample()
    df = df[df["year"] == 2022]
    saidi = df["saidi_with"].to_numpy()
    out = {}
    for k, be in breakevens.items():
        out[k] = {
            "breakeven_saidi_min_per_yr": float(be),
            "share_of_2022_utilities_above": float((saidi >= be).mean()),
            "n_above": int((saidi >= be).sum()),
        }
    return out


def density_sweep(reduction_name: str = "case_study_low") -> dict:
    """Breakeven as a function of customer density, the parameter that actually
    decides it."""
    red = PARAMS["saidi_reduction"][reduction_name]
    densities = np.array([5, 10, 20, 27, 50, 100, 200, 400])
    life = PARAMS["asset_life_years"]["value"]
    return {
        "reduction_used": reduction_name,
        "customers_per_mile": densities.tolist(),
        "breakeven_saidi_min_per_yr": [
            breakeven_saidi(PARAMS["cost_per_mile_usd"]["central"], d,
                            PARAMS["cost_per_customer_hour_usd"]["central"], red,
                            PARAMS["discount_rate"]["central"], life)
            for d in densities
        ],
    }


def _fig(dens: dict, observed_median: float) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    for name, color in (("case_study_high", PALETTE["accent"]),
                        ("case_study_low", PALETTE["without_med"]),
                        ("econometric", PALETTE["with_med"])):
        d = density_sweep(name)
        ax.plot(d["customers_per_mile"], d["breakeven_saidi_min_per_yr"],
                marker="o", lw=2.0, color=color, label=name.replace("_", " "))
    ax.axhline(observed_median, color=PALETTE["muted"], ls="--", lw=1.4)
    ax.annotate(f"median US utility SAIDI\nwith MED, 2022 ({observed_median:.0f} min/yr)",
                xy=(6, observed_median * 1.25), fontsize=9, color=PALETTE["muted"])
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("customers per line mile")
    ax.set_ylabel("baseline SAIDI needed to break even (min/yr)")
    ax.set_title("Undergrounding breakeven: the reliability-benefit assumption "
                 "moves it by 10x", loc="left", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax)
    save_figure(fig, "track5_undergrounding_breakeven")


def run(save: bool = True) -> dict:
    cpm = customers_per_mile()
    be = sweep(cpm["national_customers_per_mile"])
    df = ingest.analysis_sample()
    observed_median = float(df.loc[df["year"] == 2022, "saidi_with"].median())
    out = {
        "params": PARAMS,
        "customers_per_mile": cpm,
        "breakeven": against_observed(be),
        "density_sweep": {n: density_sweep(n) for n in
                          ("econometric", "case_study_low", "case_study_high")},
        "observed_median_saidi_with_2022": observed_median,
        "headline_ratio_case_vs_econometric": float(
            be["econometric|cost_central|voll_central"]
            / be["case_study_low|cost_central|voll_central"]),
    }
    if save:
        _fig(out["density_sweep"], observed_median)
        save_results("track5_undergrounding", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run(), indent=2, default=str))
