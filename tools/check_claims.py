#!/usr/bin/env python3
"""Pair every number quoted in the prose with the code that recomputes it.

Exits non-zero if a figure in README.md or FINDINGS.md has drifted from what the
tracks produce, if a required hedge has been deleted, or if the prose has been
sharpened into a claim the data does not support.

The point is that a retracted or overstated claim must break the build. A
finding that lives only in a README sentence stops being true silently.

    python tools/check_claims.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PROSE = ["README.md", "FINDINGS.md", "FALSIFICATION.md"]


def load(name: str) -> dict:
    path = RESULTS / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"missing {path}; run `python -m blinkrate.run_all` first")
    return json.loads(path.read_text())


def claims() -> list[tuple[str, float, float]]:
    """(quoted string that must appear in the prose, computed value, tolerance)."""
    t1 = load("track1_investment")
    t2 = load("track2_weather_split")
    t3 = load("track3_med_sensitivity")
    t4 = load("track4_cause_exclusions")
    t5 = load("track5_undergrounding")
    t6 = load("track6_ownership")
    t7 = load("track7_validation")

    s = t3["sensitivity"]["headline"]
    c = t3["coverage"]
    out: list[tuple[str, float, float]] = []

    def add(text: str, value: float, tol: float = 0.5) -> None:
        out.append((text, value, tol))

    # --- track 3, the headline ---------------------------------------------
    add(f"{s['beta_1.5']['fleet_saidi_without_med']:.0f} min/yr",
        s["beta_1.5"]["fleet_saidi_without_med"], 1.0)
    add(f"{s['beta_2.5']['fleet_saidi_without_med']:.0f} min/yr",
        s["beta_2.5"]["fleet_saidi_without_med"], 1.0)
    add(f"{s['beta_3.0']['fleet_saidi_without_med']:.0f} min/yr",
        s["beta_3.0"]["fleet_saidi_without_med"], 1.0)
    add(f"{t3['sensitivity']['fleet_range_ratio']:.2f}x",
        t3["sensitivity"]["fleet_range_ratio"], 0.02)
    add(f"{100 * c['share_exactly_zero_exclusion']:.1f}% of filings",
        100 * c["share_exactly_zero_exclusion"], 0.1)
    add(f"{100 * c['share_admissible']:.1f}%", 100 * c["share_admissible"], 0.1)
    add(f"{t3['bunching']['excess_mass_ratio']:.1f}x",
        t3["bunching"]["excess_mass_ratio"], 0.1)
    add(f"{s['beta_2.5']['expected_med_days_per_year']:.2f} qualifying days",
        s["beta_2.5"]["expected_med_days_per_year"], 0.01)

    rk = t3["ranking"]
    y = rk["by_year"][str(max(int(k) for k in rk["by_year"]))]
    add(f"is **{y['spearman']:.3f}** in 2022", y["spearman"], 0.002)
    add(f"above\n  **{max(v['spearman'] for v in rk['by_year'].values()):.3f}**",
        max(v["spearman"] for v in rk["by_year"].values()), 0.002)
    add(f"moves **{y['median_rank_move']:.0f} places**", y["median_rank_move"], 0.5)
    add(f"**{y['pct_changing_quartile']:.0f}%** change quartile",
        y["pct_changing_quartile"], 0.5)
    add(f"**{min(v['pct_changing_quartile'] for v in rk['by_year'].values()):.0f}%** to",
        min(v["pct_changing_quartile"] for v in rk["by_year"].values()), 0.5)
    add(f"a **{rk['largest_gains_latest_year']['utilities'][0]['rank_with'] - rk['largest_gains_latest_year']['utilities'][0]['rank_without']}-place** swing",
        rk["largest_gains_latest_year"]["utilities"][0]["rank_with"]
        - rk["largest_gains_latest_year"]["utilities"][0]["rank_without"], 0.5)

    # --- track 2 -----------------------------------------------------------
    add(f"{100 * t2['within_utility']['share_of_change_from_excluded_part']:.1f}% of the",
        100 * t2["within_utility"]["share_of_change_from_excluded_part"], 0.2)
    add(f"{t2['balanced_panel_utility_states']} utility-states",
        t2["balanced_panel_utility_states"], 0.5)

    # --- track 6 -----------------------------------------------------------
    add(f"{t6['by_ownership']['IOU']['median_retained_share']:.3f}",
        t6["by_ownership"]["IOU"]["median_retained_share"], 0.001)
    add(f"{t6['by_ownership']['Municipal']['median_retained_share']:.3f}",
        t6["by_ownership"]["Municipal"]["median_retained_share"], 0.001)

    # --- track 1 -----------------------------------------------------------
    ami = t1["models"]["log_saidi_without_fe"]["coefficients"]["ami_share"]
    add(f"{ami['beta']:.3f}", ami["beta"], 0.001)
    add(f"{100 * t1['variance_decomposition']['share_between_utility']:.0f}%",
        100 * t1["variance_decomposition"]["share_between_utility"], 0.5)

    # --- track 4 -----------------------------------------------------------
    add(f"{t4['los']['median_los_retained_share']:.3f}",
        t4["los"]["median_los_retained_share"], 0.001)

    # --- track 5 -----------------------------------------------------------
    be = t5["breakeven"]["case_study_high|cost_central|voll_central"]
    add(f"{be['breakeven_saidi_min_per_yr']:,.0f} min/yr",
        be["breakeven_saidi_min_per_yr"], 1.0)
    add(f"{t5['customers_per_mile']['national_customers_per_mile']:.1f} customers per",
        t5["customers_per_mile"]["national_customers_per_mile"], 0.05)

    # --- track 7 -----------------------------------------------------------
    add(f"{100 * t7['caidi_identity']['with_med']['share_within_tolerance']:.0f}%",
        100 * t7["caidi_identity"]["with_med"]["share_within_tolerance"], 0.5)

    # --- track 8: the falsification results are claims too --------------------
    # FALSIFICATION.md is where a result gets retracted or scoped, which makes it
    # the file most likely to drift out of agreement with the code and the one
    # where drift does the most damage.
    t8 = load("track8_falsification")
    a1b, a2 = t8["A1b_heavy_tail_matched"], t8["A2_mean_vs_median"]
    a3, a4 = t8["A3_bunching_specs"], t8["A4_track2_trimmed"]
    a5, a6 = t8["A5_ownership_large_only"], t8["A6_track1_power"]

    add(f"up to {t8['A1_heavy_tail']['max_abs_shift_in_r']:.2f}",
        t8["A1_heavy_tail"]["max_abs_shift_in_r"], 0.01)
    add(f"{a1b['sweep_ratio_spread_x']:.2f}x across these distributions",
        a1b["sweep_ratio_spread_x"], 0.02)
    add(f"reaches {a2['max_gap']:.3f}", a2["max_gap"], 0.002)
    add(f"median {a3['median_excess_mass']:.2f}", a3["median_excess_mass"], 0.05)
    add(f"in {a3['n_specs_with_ci_lower_above_1']} of them",
        a3["n_specs_with_ci_lower_above_1"], 0.5)
    add(f"{a4['n_trimmed']} utility-states): "
        f"{100 * a4['trimmed_share_from_excluded']:.1f}%",
        a4["n_trimmed"], 0.5)
    add(f"{100 * a4['unweighted_share_from_excluded']:.1f}%",
        100 * a4["unweighted_share_from_excluded"], 0.2)
    add(f"{abs(a5['all']['iou_minus_coop_median_r']):.3f} below",
        abs(a5["all"]["iou_minus_coop_median_r"]), 0.002)
    add(f"| {a5['above_median_size']['iou_minus_coop_median_r']:.3f} |",
        a5["above_median_size"]["iou_minus_coop_median_r"], 0.002)
    add(f"{a6['mde_80pct_power']:.3f} log points", a6["mde_80pct_power"], 0.005)
    add(f"{abs(a6['mde_as_pct_saidi_change']):.1f}% SAIDI change",
        abs(a6["mde_as_pct_saidi_change"]), 0.2)
    add(f"{100 * a6['ami_share_variation']['share_at_100pct']:.1f}% of 2022",
        100 * a6["ami_share_variation"]["share_at_100pct"], 0.2)

    # the conditional ownership numbers, quoted in both FINDINGS and FALSIFICATION
    cond = t6["conditional"]
    add(f"{100 * abs(cond['zero_exclusion_no_size']['IOU_vs_Coop']):.1f} points",
        100 * abs(cond["zero_exclusion_no_size"]["IOU_vs_Coop"]), 0.2)
    add(f"{100 * abs(cond['zero_exclusion_with_size']['IOU_vs_Coop']):.1f} points",
        100 * abs(cond["zero_exclusion_with_size"]["IOU_vs_Coop"]), 0.2)

    # the implied-sigma spread that scopes A2's verdict
    q = t3["coverage"]["implied_sigma_quantiles"]
    add(f"{q['10']:.2f} to {q['90']:.2f}", q["10"], 0.01)

    return out


REQUIRED_HEDGES = [
    # track 3 must never be described as a measurement
    ("model-implied", "track 3's sensitivity is model-implied, not measured; "
                      "the qualifier must stay in the prose"),
    ("log-normal", "the log-normality assumption inherited from IEEE 1366 must "
                   "be named"),
    # track 2 must keep its blocker
    ("weather severity", "track 2 cannot separate weather from classification "
                         "without an external severity index; say so"),
    # track 1 must keep its substitution
    ("deployment", "track 1 regresses physical deployment, not spending; the "
                   "substitution must remain visible"),
    ("FERC Form 1", "the missing capex source must be named"),
]

FORBIDDEN = [
    (r"\bprove[sd]?\b", "nothing here proves anything"),
    (r"\bgaming\b(?!\s*(?:question|hypothesis|story|explanation|would))",
     "'gaming' asserts intent this data cannot establish; use the hedged form"),
    (r"utilities manipulate", "asserts intent the data cannot establish"),
    (r"\bcauses?\s+lower\s+SAIDI\b", "track 1 is a cross-section, not causal"),
    (r"\ball utilities\b", "universal quantifier; the sample is 3,427 "
                           "utility-state-years across 4 filing years"),
    (r"\bmeasured\s+sensitivity\b", "the sensitivity is model-implied"),
]


def main() -> int:
    prose = {}
    for name in PROSE:
        path = ROOT / name
        if not path.exists():
            print(f"MISSING PROSE FILE: {name}")
            return 1
        prose[name] = path.read_text()
    blob = "\n".join(prose.values())

    failures = []

    for text, value, tol in claims():
        nums = re.findall(r"-?\d[\d,]*\.?\d*", text)
        # Anchor on digit boundaries. Plain substring matching lets a claim of
        # "18.3 points" be satisfied by the unrelated "8.3 points" elsewhere in
        # the prose, which is exactly the kind of false pass a guard must not
        # have.
        anchored = re.escape(text)
        if nums:
            anchored = anchored.replace(
                re.escape(nums[0]), r"(?<![\d.])" + re.escape(nums[0]) + r"(?![\d])", 1)
        if re.search(anchored, blob):
            if not nums:
                continue
            quoted = float(nums[0].replace(",", ""))
            if abs(quoted - value) > tol:
                failures.append(
                    f"drift: prose says {quoted} in {text!r}, code says "
                    f"{value:.4f} (tolerance {tol})")
            continue

        # The exact string is absent. Distinguish an edited NUMBER from a deleted
        # CLAIM, because those need different fixes: one means rerun the tracks,
        # the other means the prose lost a result. Rebuild the claim with its
        # leading number wildcarded and look for that.
        if nums:
            pattern = re.escape(text).replace(
                re.escape(nums[0]),
                r"(?<![\d.])(-?\d[\d,]*\.?\d*)(?![\d])", 1)
            # Several places in the prose can match the wildcarded pattern (a
            # claim of "18.2 points" wildcards to something that also matches an
            # unrelated "8.3 points"). Report the candidate closest to the
            # computed value, so the diagnostic points at the line that actually
            # needs editing.
            cands = [(abs(float(m.group(1).replace(",", "")) - value), m)
                     for m in re.finditer(pattern, blob)]
            if cands:
                _, found = min(cands, key=lambda t: t[0])
                quoted = float(found.group(1).replace(",", ""))
                failures.append(
                    f"drift: prose says {quoted} in {found.group(0)!r}, code says "
                    f"{value:.4f} (tolerance {tol})")
                continue
        failures.append(f"claim not found in prose: {text!r} (computed {value})")

    for token, why in REQUIRED_HEDGES:
        if token.lower() not in blob.lower():
            failures.append(f"required hedge missing ({token!r}): {why}")

    for pattern, why in FORBIDDEN:
        for name, text in prose.items():
            # the retraction blockquote is where superseded claims are quoted
            stripped = re.sub(r"^> .*$", "", text, flags=re.MULTILINE)
            m = re.search(pattern, stripped, flags=re.IGNORECASE)
            if m:
                failures.append(f"forbidden phrasing in {name}: {m.group(0)!r} - {why}")

    n_claims = len(claims())
    if failures:
        print(f"FAILED: {len(failures)} problem(s) across {n_claims} checked claims\n")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {n_claims} claims match the results, "
          f"{len(REQUIRED_HEDGES)} hedges present, "
          f"{len(FORBIDDEN)} overclaim patterns absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
