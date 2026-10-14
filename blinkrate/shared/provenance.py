"""Schema-level separation of what was filed from what was modelled.

Every number this repository reports is one of two kinds, and a reader deserves
to know which without reading the method:

  filed_data        computed directly from EIA-861 filings by counting, ranking,
                    averaging or regressing. No distributional assumption about
                    daily outages is involved. If EIA's arithmetic is right, this
                    is right.
  model_implied     depends on inverting IEEE 1366's exclusion under an assumed
                    daily-SAIDI distribution. Log-normal by default, which is the
                    standard's own assumption, and attacks A1, A10 and A11 show
                    how much these numbers move when it is relaxed.

Three more kinds cover the rest:

  outage_map_data   computed from two utilities' public outage maps, archived by
                    git scraping (attack A14). Measured, and free of the
                    distributional assumption, but an estimate of customers out
                    rather than the SAIDI a utility reports.
  literature_model  a payback model whose inputs are published parameters rather
                    than filings (track 5).
  meta              status text, blockers, substitution notes, audit counts.

The prose already labels each answer "Basis: filed data" or "Basis:
model-implied". This makes the same split structural. `stamp()` writes a
`_provenance` block into every results file, and raises if a track tries to save
a result key that has not been declared here, so a new number cannot be
published without someone deciding which kind it is.

Blocks are labelled by a default kind plus named exceptions, because several
real results mix the two. A8's part one compares a model-implied sweep against a
filed cross-utility spread; the ratio inherits the model, the spread does not.
Exceptions apply to that field name wherever it appears inside the block.
"""

from __future__ import annotations

FILED = "filed_data"
MODEL = "model_implied"
OUTAGE = "outage_map_data"
LIT = "literature_model"
META = "meta"

KINDS = {
    FILED: ("computed directly from EIA-861 filings; no assumption about the "
            "distribution of daily outages"),
    MODEL: ("depends on inverting IEEE 1366's exclusion under an assumed "
            "daily-SAIDI distribution, log-normal unless stated; see attacks A1, "
            "A10 and A11 for how far these move when it is relaxed"),
    OUTAGE: ("computed from public outage-map snapshots archived by git "
             "scraping (PG&E 2019-2022, FPL 2019-2023); estimated customers out, "
             "not reported IEEE 1366 SAIDI"),
    LIT: "a payback model driven by published literature parameters",
    META: "status, blockers, substitutions and audit counts",
}


def _b(default: str, **exceptions: str) -> dict:
    return {"default": default, "exceptions": exceptions}


# The sigma-dependent coverage fields rest on the calibration surface; the
# zero-exclusion count does not.
_COVERAGE_MODEL = dict(share_admissible=MODEL, n_admissible=MODEL,
                       share_too_clean=MODEL, n_too_clean=MODEL,
                       share_too_excluded=MODEL, n_too_excluded=MODEL,
                       r_max_modelable=MODEL, r_min_modelable=MODEL,
                       implied_sigma_quantiles=MODEL)

REGISTRY: dict[str, dict[str, dict]] = {
    "track1_investment": {
        "substitution": _b(META),
        "cross_sections": _b(FILED),
        "within_utility": _b(FILED),
        "long_difference": _b(FILED),
        "variance_decomposition": _b(FILED),
    },
    "track2_weather_split": {
        "blocker": _b(META),
        "balanced_panel_utility_states": _b(FILED),
        "trend": _b(FILED),
        "gradual_or_step": _b(FILED),
        "within_utility": _b(FILED),
        "within_utility_consecutive": _b(FILED),
        "exclusion_entry": _b(FILED),
        "spike_geography": _b(FILED),
        "storm_state_sensitivity": _b(FILED),
    },
    "track3_med_sensitivity": {
        "coverage": _b(FILED, **_COVERAGE_MODEL),
        "sensitivity": _b(MODEL),
        "elasticity": _b(MODEL),
        "bunching": _b(FILED),
        "standard_choice": _b(FILED),
        "ranking": _b(FILED),
        # observed shares are filed data; what they are compared against is the
        # standard's own design frequency, which is a model
        "zero_exclusion_benchmark": _b(FILED, benchmarks=MODEL,
                                       generous_ceiling=MODEL,
                                       multiple_of_generous_benchmark=MODEL,
                                       large_ieee_within_benchmark_range=MODEL),
    },
    "track4_cause_exclusions": {
        "status": _b(META),
        "blocker": _b(META),
        "substituted_analysis": _b(META),
        "los": _b(FILED),
    },
    "track5_undergrounding": {
        "params": _b(LIT),
        # EIA customer counts over a published line-mile figure
        "customers_per_mile": _b(LIT),
        "breakeven": _b(LIT),
        "density_sweep": _b(LIT),
        "headline_ratio_case_vs_econometric": _b(LIT),
        "observed_median_saidi_with_2022": _b(FILED),
    },
    "track6_ownership": {
        "by_ownership": _b(FILED, median_implied_sigma=MODEL),
        "conditional": _b(FILED),
        "size_deciles": _b(FILED),
    },
    "track7_validation": {
        "caidi_identity": _b(FILED),
        "closed_form_vs_procedure": _b(MODEL),
        "round_trip": _b(MODEL),
        "hand_checks": _b(FILED),
        "rejected_rows": _b(META),
        "duplicate_filings": _b(META),
    },
    "track8_falsification": {
        "A1_heavy_tail": _b(MODEL),
        "A1b_heavy_tail_matched": _b(MODEL),
        "A2_mean_vs_median": _b(MODEL),
        "A3_bunching_specs": _b(FILED),
        "A4_track2_trimmed": _b(FILED),
        "A5_ownership_large_only": _b(FILED),
        "A6_track1_power": _b(FILED),
        "A7_leave_one_state_out": _b(FILED, fleet_range_ratio=MODEL,
                                     fleet_saidi_at_2_5=MODEL),
        "A8_stated_falsification_criterion": _b(
            FILED, part1_rule_vs_cross_utility_spread=MODEL,
            cross_utility_spread_x=FILED),
        "A9_leave_one_utility_out": _b(FILED),
        "A10_tail_breaking_point": _b(MODEL, cross_utility_spread_p90_p10=FILED),
        "A11_threshold_window": _b(MODEL, cross_utility_spread_p90_p10=FILED),
        "A12_pareto_tail": _b(MODEL, cross_utility_spread_p90_p10=FILED,
                              working_group_observed_range=LIT),
        "A13_evidence_grounded_window": _b(MODEL, cross_utility_spread_p90_p10=FILED,
                                           windows_in_med_days_per_year=LIT),
        # measured on outage maps, set against what each model predicts from
        # the same year's retained share; the predictions and anything compared
        # with them inherit the model
        "A14_real_daily_outages": _b(
            OUTAGE, sources=META, rules=META, caveats=META, reading=META, note=META,
            window_beta=MODEL, nominal_med_days_per_year=MODEL,
            laplace_med_days_per_year=MODEL, windows_in_med_days_per_year=LIT,
            lognormal_predicted_x=MODEL, t_nu15_predicted_x=MODEL,
            laplace_predicted_x=MODEL, lognormal_over_measured=MODEL,
            closest_model=MODEL, n_lognormal_overstates=MODEL, n_model_evaluable=MODEL,
            lognormal_over_measured_range=MODEL, closest_model_counts=MODEL,
            filed_saidi_with=FILED, filed_saidi_without=FILED,
            filed_customers=FILED),
    },
    "track9_aggregation": {
        "by_year": _b(FILED),
        "concentration": _b(FILED),
        "combined_space": _b(MODEL),
        "trend_by_aggregator": _b(FILED),
        "latest_year_spread": _b(FILED),
    },
}


class ProvenanceError(ValueError):
    """A result was saved without being declared filed or model-implied."""


def stamp(name: str, payload: dict) -> dict:
    """Return payload with a `_provenance` block, refusing undeclared keys."""
    if name not in REGISTRY:
        raise ProvenanceError(
            f"results file {name!r} has no provenance registry entry; add one "
            "to blinkrate/shared/provenance.py before publishing its numbers")
    declared = REGISTRY[name]
    keys = {k for k in payload if not k.startswith("_")}
    undeclared = keys - set(declared)
    if undeclared:
        raise ProvenanceError(
            f"{name}: result keys {sorted(undeclared)} are not declared as "
            "filed_data or model_implied; declare them in provenance.REGISTRY")
    stale = set(declared) - keys
    if stale:
        raise ProvenanceError(
            f"{name}: registry declares {sorted(stale)} but the track no longer "
            "produces them; remove them so the registry stays truthful")
    out = dict(payload)
    out["_provenance"] = {
        "kinds": KINDS,
        "blocks": {k: declared[k] for k in sorted(keys)},
    }
    return out


def kind_of(name: str, block: str, field: str | None = None) -> str:
    """The declared kind of a block, or of a named field inside it."""
    b = REGISTRY[name][block]
    if field is not None and field in b["exceptions"]:
        return b["exceptions"][field]
    return b["default"]
