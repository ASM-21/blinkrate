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
PROSE = ["README.md", "FINDINGS.md", "FALSIFICATION.md", "LITERATURE.md",
         "CHANGELOG.md"]


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
    t8 = load("track8_falsification")
    t9 = load("track9_aggregation")

    out: list[tuple[str, float, float]] = []

    def add(text: str, value: float, tol: float = 0.5) -> None:
        # The checked value is the FIRST number in `text`. A claim string that
        # opens with an identifier containing digits ("A10's row gives 6.04x")
        # compares the wrong number; lead with the value or with plain words.
        out.append((text, value, tol))

    # --- Q1: the threshold sweep -------------------------------------------
    s3 = t3["sensitivity"]["headline"]
    for b in ("1.5", "2.0", "2.5", "3.0"):
        add(f"{s3[f'beta_{b}']['fleet_saidi_without_med']:.0f} min/yr",
            s3[f"beta_{b}"]["fleet_saidi_without_med"], 1.0)
    add(f"{t3['sensitivity']['fleet_range_ratio']:.2f}x range",
        t3["sensitivity"]["fleet_range_ratio"], 0.02)
    add(f"{s3['beta_2.5']['expected_med_days_per_year']:.2f} qualifying days",
        s3["beta_2.5"]["expected_med_days_per_year"], 0.01)

    # --- Q2: the mass point ------------------------------------------------
    c = t3["coverage"]
    add(f"{100 * c['share_exactly_zero_exclusion']:.1f}% of filings",
        100 * c["share_exactly_zero_exclusion"], 0.1)
    add(f"**{100 * c['share_admissible']:.1f}%** of filings",
        100 * c["share_admissible"], 0.1)
    add(f"**{t3['bunching']['excess_mass_ratio']:.1f}x** the counterfactual",
        t3["bunching"]["excess_mass_ratio"], 0.1)
    sc = t3["standard_choice"]
    add(f"**{sc['Other']['median_retained_share']:.3f}** against",
        sc["Other"]["median_retained_share"], 0.002)
    add(f"**{sc['IEEE']['median_retained_share']:.3f}**",
        sc["IEEE"]["median_retained_share"], 0.002)
    add(f"{100 * sc['switchers']['share_switched']:.1f}% of utility-states switched",
        100 * sc["switchers"]["share_switched"], 0.2)

    # --- Q3: the ranking ---------------------------------------------------
    rk = t3["ranking"]
    add(f"**{rk['spearman_range'][0]:.3f}** to", rk["spearman_range"][0], 0.003)
    add(f"**{rk['spearman_range'][1]:.3f}**", rk["spearman_range"][1], 0.003)
    add(f"{rk['pct_changing_quartile_range'][0]:.0f} to "
        f"{rk['pct_changing_quartile_range'][1]:.0f}% change quartile",
        rk["pct_changing_quartile_range"][0], 0.6)
    g0 = rk["largest_gains_latest_year"]["utilities"][0]
    add(f"**{g0['rank_with'] - g0['rank_without']}-place** swing",
        g0["rank_with"] - g0["rank_without"], 0.5)

    # --- Q4: weather vs classification -------------------------------------
    add(f"**{t2['balanced_panel_utility_states']} utility-states**",
        t2["balanced_panel_utility_states"], 0.5)
    st = t2["gradual_or_step"]
    add(f"**{st['without_med_slope_min_per_year']:.2f} min/yr**",
        st["without_med_slope_min_per_year"], 0.02)
    sg = t2["spike_geography"]["by_transition"]["2016_2017"]
    add(f"**{sg['d_excluded_hurricane_cw']:.1f}** minutes inside",
        sg["d_excluded_hurricane_cw"], 0.2)
    add(f"**{sg['d_excluded_other_cw']:.1f}** elsewhere",
        sg["d_excluded_other_cw"], 0.2)
    add(f"**{t2['spike_geography']['largest_excluded_gap_minutes']:.1f}** minutes",
        t2["spike_geography"]["largest_excluded_gap_minutes"], 0.2)
    add(f"is {t2['spike_geography']['second_largest_excluded_gap_minutes']:.1f}",
        t2["spike_geography"]["second_largest_excluded_gap_minutes"], 0.2)
    ee = t2["exclusion_entry"]
    add(f"**{abs(ee['trend_pct_points_per_year']):.2f}** percentage points per year",
        abs(ee["trend_pct_points_per_year"]), 0.02)
    add(f"{100 * ee['started_excluding']:.1f}% of utilities went",
        100 * ee["started_excluding"], 0.2)
    add(f"{100 * ee['stopped_excluding']:.1f}% moving the other way",
        100 * ee["stopped_excluding"], 0.2)
    add(f"**{100 * t2['within_utility']['share_of_change_from_excluded_part']:.1f}%** of the",
        100 * t2["within_utility"]["share_of_change_from_excluded_part"], 0.2)
    a4 = t8["A4_track2_trimmed"]
    add(f"window | {100 * t2['within_utility_consecutive']['share_of_change_from_excluded_part']:.1f}%",
        100 * t2["within_utility_consecutive"]["share_of_change_from_excluded_part"], 0.2)
    add(f"unweighted | {100 * a4['unweighted_share_from_excluded']:.1f}%",
        100 * a4["unweighted_share_from_excluded"], 0.2)
    add(f"trimmed | {100 * a4['trimmed_share_from_excluded']:.1f}%",
        100 * a4["trimmed_share_from_excluded"], 0.2)

    # --- Q4 / A7: the state dependence that rewrote Q4 ----------------------
    a7 = t8["A7_leave_one_state_out"]
    ss = t2["storm_state_sensitivity"]
    add(f"**{100 * a7['florida']['share_from_excluded']:.1f}%**",
        100 * a7["florida"]["share_from_excluded"], 0.2)
    add(f"**{100 * ss['hurricane_states_dropped']['share_from_excluded_cw']:.1f}%**",
        100 * ss["hurricane_states_dropped"]["share_from_excluded_cw"], 0.2)
    add(f"from {ss['all_states']['share_from_excluded_cw']:.3f} to "
        f"{ss['hurricane_states_dropped']['share_from_excluded_cw']:.3f}",
        ss["all_states"]["share_from_excluded_cw"], 0.002)
    add(f"only\nfrom {ss['all_states']['share_from_excluded_unweighted']:.3f} to "
        f"{ss['hurricane_states_dropped']['share_from_excluded_unweighted']:.3f}",
        ss["all_states"]["share_from_excluded_unweighted"], 0.002)
    add(f"**{ss['all_states']['everyday_slope']:.2f}** min/yr with all states",
        ss["all_states"]["everyday_slope"], 0.02)
    add(f"**{ss['hurricane_states_dropped']['everyday_slope']:.2f}** min/yr with the",
        ss["hurricane_states_dropped"]["everyday_slope"], 0.02)
    add(f"by under {max(v['max_pct_shift'] for k, v in a7['summary'].items() if k != 'share_from_excluded'):.1f}%",
        max(v["max_pct_shift"] for k, v in a7["summary"].items()
            if k != "share_from_excluded"), 0.6)

    # --- Q5: capital deployment --------------------------------------------
    wu = t1["within_utility"]
    add(f"**{wu['coefficients']['ami_share']['beta']:+.3f}**",
        wu["coefficients"]["ami_share"]["beta"], 0.002)
    add(f"**{wu['n_moving_ami_gt_0_50']}** move their AMI",
        wu["n_moving_ami_gt_0_50"], 0.5)
    add(f"{wu['n_utility_states']} utility-states are observed",
        wu["n_utility_states"], 0.5)
    add(f"{t1['cross_sections']['2016']['coefficients']['ami_share']['beta']:.3f}",
        t1["cross_sections"]["2016"]["coefficients"]["ami_share"]["beta"], 0.002)
    add(f"{t1['cross_sections']['2022']['coefficients']['ami_share']['beta']:.3f}",
        t1["cross_sections"]["2022"]["coefficients"]["ami_share"]["beta"], 0.002)
    gc = t1["long_difference"]["group_comparison"]
    add(f"**{gc['pct_saidi_difference']:.1f}%** relative",
        gc["pct_saidi_difference"], 0.2)
    add(f"the {gc['n_rollout']} utilities that rolled", gc["n_rollout"], 0.5)
    add(f"**{100 * t1['variance_decomposition']['share_between_utility']:.0f}%** of the variance",
        100 * t1["variance_decomposition"]["share_between_utility"], 0.6)

    # --- Q6: ownership -----------------------------------------------------
    o6, cd = t6["by_ownership"], t6["conditional"]
    add(f"**{o6['IOU']['median_retained_share']:.3f}** for", 
        o6["IOU"]["median_retained_share"], 0.002)
    add(f"**{o6['Municipal']['median_retained_share']:.3f}** municipal",
        o6["Municipal"]["median_retained_share"], 0.002)
    add(f"{100 * abs(cd['zero_exclusion_with_size']['IOU_vs_Coop']):.1f} points at "
        f"p = {cd['zero_exclusion_with_size']['IOU_p']:.3f}",
        100 * abs(cd["zero_exclusion_with_size"]["IOU_vs_Coop"]), 0.2)
    add(f"**{abs(cd['retained_share_with_size']['IOU_vs_Coop']):.3f}** lower",
        abs(cd["retained_share_with_size"]["IOU_vs_Coop"]), 0.002)
    a5 = t8["A5_ownership_large_only"]
    add(f"{abs(a5['all']['iou_minus_coop_median_r']):.3f} to "
        f"{abs(a5['above_median_size']['iou_minus_coop_median_r']):.3f}",
        abs(a5["all"]["iou_minus_coop_median_r"]), 0.002)

    # --- Q7: validation ----------------------------------------------------
    ci = t7["caidi_identity"]["with_med"]
    add(f"**{100 * ci['share_within_tolerance']:.2f}%** of {ci['n_checked']:,}",
        100 * ci["share_within_tolerance"], 0.01)
    add(f"{t7['rejected_rows']['n']} rows fail", t7["rejected_rows"]["n"], 0.5)

    # --- smaller results ---------------------------------------------------
    los = t4["los"]
    add(f"{100 * los['share_of_ieee_reporting_los']:.1f}% of IEEE-standard",
        100 * los["share_of_ieee_reporting_los"], 0.2)
    add(f"**{los['median_los_retained_share']:.3f}**",
        los["median_los_retained_share"], 0.002)
    add(f"{100 * los['stacked_med_and_los']['median_combined_retained']:.1f}% of its raw",
        100 * los["stacked_med_and_los"]["median_combined_retained"], 0.2)
    be = t5["breakeven"]["case_study_high|cost_central|voll_central"]
    add(f"**{be['breakeven_saidi_min_per_yr']:,.0f} min/yr**",
        be["breakeven_saidi_min_per_yr"], 1.0)
    add(f"**{t5['customers_per_mile']['national_customers_per_mile']:.1f} customers per**",
        t5["customers_per_mile"]["national_customers_per_mile"], 0.05)
    add(f"moves breakeven by {t5['headline_ratio_case_vs_econometric']:.1f}x",
        t5["headline_ratio_case_vs_econometric"], 0.05)

    # --- falsification -----------------------------------------------------
    add(f"spans **{t8['A1b_heavy_tail_matched']['sweep_ratio_spread_x']:.2f}x** across",
        t8["A1b_heavy_tail_matched"]["sweep_ratio_spread_x"], 0.02)
    a3 = t8["A3_bunching_specs"]
    add(f"survives\n{a3['n_specs_with_ci_lower_above_1']} of {a3['n_specifications']}",
        a3["n_specs_with_ci_lower_above_1"], 0.5)

    # --- Q8: the aggregation rule ------------------------------------------
    y22 = t9["by_year"]["2022"]
    add(f"to {y22['with_med']['unweighted_mean']:.1f} min/yr with major event days",
        y22["with_med"]["unweighted_mean"], 0.2)
    add(f"from {y22['with_med']['median_utility']:.1f}",
        y22["with_med"]["median_utility"], 0.2)
    add(f"a {y22['with_med_spread_x']:.2f}x range",
        y22["with_med_spread_x"], 0.02)
    for k in ("customer_weighted_mean", "customer_weighted_median",
              "trimmed_customer_weighted_mean",
              "winsorized_customer_weighted_mean"):
        add(f"| {y22['with_med'][k]:.1f} | {y22['without_med'][k]:.1f} |",
            y22["with_med"][k], 0.2)
    cc = t9["concentration"]["2022"]
    add(f"**{100 * cc['with_med']['top_1_share']:.1f}%** of national",
        100 * cc["with_med"]["top_1_share"], 0.2)
    add(f"supply **{100 * cc['with_med']['top_10_share']:.1f}%**",
        100 * cc["with_med"]["top_10_share"], 0.2)
    add(f"is **{cc['with_med_gini']:.3f}**", cc["with_med_gini"], 0.002)
    cs9 = t9["combined_space"]
    add(f"**{cs9['min']:.1f}** to **{cs9['max']:.1f}** min/yr",
        cs9["min"], 0.2)
    add(f"a **{cs9['range_x']:.2f}x** range", cs9["range_x"], 0.02)
    add(f"lands at {cs9['standard_choice']:.1f}", cs9["standard_choice"], 0.2)
    tb = t9["trend_by_aggregator"]
    add(f"from {tb['slope_range'][0]:.2f} to {tb['slope_range'][1]:.2f} min/yr",
        tb["slope_range"][0], 0.02)
    add(f"spans {tb['slope_range'][0]:.2f} to {tb['slope_range'][1]:.2f} minutes per year",
        tb["slope_range"][0], 0.02)

    # --- A8 / A9: the stated criterion, and the utility-level jackknife -----
    a8 = t8["A8_stated_falsification_criterion"]
    p1 = a8["part1_rule_vs_cross_utility_spread"]
    strat = a8["part2_reversal_within_exposure"]["by_stratum"]
    add(f"median of **{p1['own_sweep_median_x']:.2f}x**",
        p1["own_sweep_median_x"], 0.02)
    add(f"range {p1['own_sweep_iqr_x'][0]:.2f}x to {p1['own_sweep_iqr_x'][1]:.2f}x",
        p1["own_sweep_iqr_x"][0], 0.02)
    add(f"is **{p1['cross_utility_spread_x']['p90_over_p10']:.2f}x**",
        p1["cross_utility_spread_x"]["p90_over_p10"], 0.02)
    add(f"and {p1['cross_utility_spread_x']['p75_over_p25']:.2f}x across",
        p1["cross_utility_spread_x"]["p75_over_p25"], 0.02)
    add(f"**{p1['ratio_rule_to_spread']:.2f}** times the whole",
        p1["ratio_rule_to_spread"], 0.02)
    add(f"quartile change runs {strat['low_pre_exposure']['pct_changing_quartile']:.0f}%, "
        f"{strat['mid_pre_exposure']['pct_changing_quartile']:.0f}% and "
        f"{strat['high_pre_exposure']['pct_changing_quartile']:.0f}%",
        strat["low_pre_exposure"]["pct_changing_quartile"], 0.6)
    add(f"and {strat['non_hurricane_states']['pct_changing_quartile']:.0f}% within "
        "non-hurricane states",
        strat["non_hurricane_states"]["pct_changing_quartile"], 0.6)

    a9 = t8["A9_leave_one_utility_out"]
    add(f"supplies {100 * a9['largest_contributor']['share_of_national_customer_minutes']:.1f}% "
        "of national",
        100 * a9["largest_contributor"]["share_of_national_customer_minutes"], 0.2)
    add(f"{a9['by_drop']['drop_top_10']['spread_x']:.2f}x after",
        a9["by_drop"]["drop_top_10"]["spread_x"], 0.02)

    # --- A10: the breaking point that made the headline conditional ----------
    a10 = t8["A10_tail_breaking_point"]["by_tail"]
    add(f"where the ratio is {a10['t_nu30']['ratio_to_cross_utility_spread']:.2f}",
        a10["t_nu30"]["ratio_to_cross_utility_spread"], 0.02)
    add(f"where it is\n{a10['t_nu15']['ratio_to_cross_utility_spread']:.2f}",
        a10["t_nu15"]["ratio_to_cross_utility_spread"], 0.02)
    add(f"row gives {a10['lognormal']['median_own_sweep_x']:.2f}x against",
        a10["lognormal"]["median_own_sweep_x"], 0.02)

    return out


# Phrases that must survive in the prose. Each exists because deleting it would
# make a true statement into a false one, and nothing else would notice.
REQUIRED_DISCLAIMER = [
    "Independent personal project",
    "not affiliated with, reviewed by, or",
    "produced on behalf of PPL Electric Utilities",
    "no non-public, proprietary, customer, or",
]

REQUIRED_PRIOR_ART = [
    ("LITERATURE.md", "the literature record must stay linked from the prose"),
    ("corroboration", "Q1 and Q2 are corroboration of an established critique; "
                      "saying otherwise overstates the contribution"),
    ("LBNL", "LBNL's prior work on major-event definitions must stay cited"),
    ("2013", "the IEEE 2013 threshold-instability letter must stay cited"),
    ("APPA", "the APPA customer-weighting convention must stay cited for Q8"),
]

# Novelty language. The critique here is not new and the prose must not imply it.
FORBIDDEN_NOVELTY = [
    r"\bnovel\b", r"for the first time", r"we discovered", r"\bunprecedented\b",
    r"\bnever before\b", r"\bfirst to (?:show|find|measure|document)\b",
]

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
    ("conditional on the tails of daily outages",
     "A10 found the headline comparison breaks under mildly heavy tails; the "
     "README must say so where it makes the comparison"),
    ("Basis: model-implied", "FINDINGS must label model-implied answers as such"),
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
    (r"more than the whole\s+industry spans",
     "A10 showed this holds only under near-log-normal tails; state it as "
     "conditional or quote it in a blockquote as superseded"),
]


def _flatten(text: str) -> str:
    """Runs of whitespace (including newlines) become one space."""
    return re.sub(r"\s+", " ", text)


def main() -> int:
    prose = {}
    for name in PROSE:
        path = ROOT / name
        if not path.exists():
            print(f"MISSING PROSE FILE: {name}")
            return 1
        prose[name] = path.read_text()
    # Collapse whitespace before matching. A claim must not fail because the
    # sentence happened to wrap between two of its words, which is otherwise a
    # constant source of false alarms every time the prose is reflowed.
    # Blockquote markers are stripped too. Retractions live in blockquotes and
    # their numbers still have to match the code, otherwise the one place the
    # prose is most likely to go stale is the one place nothing checks.
    blob = _flatten(re.sub(r"^>\s?", "", "\n".join(prose.values()),
                           flags=re.MULTILINE))

    failures = []

    for raw_text, value, tol in claims():
        text = _flatten(raw_text)
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
            # The exact string being present somewhere is not enough. The same
            # figure is often quoted in two files, and a stale second copy
            # would otherwise pass forever because the first copy satisfies the
            # match. So every occurrence of the claim's context is checked, but
            # only when the context is distinctive: a claim whose only context
            # is a unit ("37 min/yr") matches every other figure in that unit,
            # which the first version of this check did 1,847 times.
            context = re.sub(r"[*_|`]", "", text.replace(nums[0], "", 1)).strip()
            if len(context) < 12 or len(re.findall(r"[A-Za-z]{2,}", context)) < 2:
                continue
            pattern = re.escape(text).replace(
                re.escape(nums[0]),
                r"(?<![\d.])(-?\d[\d,]*\.?\d*)(?![\d])", 1)
            for m in re.finditer(pattern, blob):
                other = float(m.group(1).replace(",", ""))
                if abs(other - value) > tol:
                    failures.append(
                        f"stale copy: prose also says {other} in "
                        f"{m.group(0)!r}, code says {value:.4f}")
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

    # The disclaimer is a wrapped markdown blockquote, so its phrases span line
    # breaks and "> " prefixes. blob is already whitespace-normalised and
    # blockquote-stripped, which is the only reason a substring check works.
    readme = _flatten(re.sub(r"^>\s?", "", (ROOT / "README.md").read_text(),
                             flags=re.MULTILINE))
    for phrase in REQUIRED_DISCLAIMER:
        if phrase.lower() not in readme.lower():
            failures.append(
                f"independence disclaimer missing or altered: {phrase!r}")

    lit = ROOT / "LITERATURE.md"
    if not lit.exists():
        failures.append("LITERATURE.md is missing; the prior-art record is "
                        "part of the claim, not an optional extra")
    for token, why in REQUIRED_PRIOR_ART:
        if token.lower() not in blob.lower():
            failures.append(f"prior-art attribution missing ({token!r}): {why}")

    for pattern in FORBIDDEN_NOVELTY:
        m = re.search(pattern, blob, flags=re.IGNORECASE)
        if m:
            failures.append(
                f"novelty language: {m.group(0)!r} - the 2.5-beta critique is "
                "established prior work (see LITERATURE.md)")

    for token, why in REQUIRED_HEDGES:
        if token.lower() not in blob.lower():
            failures.append(f"required hedge missing ({token!r}): {why}")

    # Figure titles and captions are prose the reader sees, and until a
    # track 9 title claimed "the slope does not [depend on the rule]" — which
    # that track's own numbers contradict — nothing checked them. Only the
    # string literals inside the plotting helpers are scanned, so ordinary
    # identifiers and comments do not trip it.
    fig_text = []
    for src in sorted((ROOT / "blinkrate").glob("track*.py")):
        body = src.read_text()
        for m in re.finditer(r"(?:set_title|fig\.text|ax\.text|annotate)\((.*?)\)",
                             body, flags=re.DOTALL):
            fig_text.append(f"{src.name}: {m.group(1)}")
    fig_blob = _flatten("\n".join(fig_text))
    for pattern, why in FORBIDDEN:
        m = re.search(pattern, fig_blob, flags=re.IGNORECASE)
        if m:
            failures.append(f"forbidden phrasing in a figure: {m.group(0)!r} - {why}")

    for pattern, why in FORBIDDEN:
        for name, text in prose.items():
            # the retraction blockquote is where superseded claims are quoted
            stripped = re.sub(r"^> .*$", "", text, flags=re.MULTILINE)
            m = re.search(pattern, stripped, flags=re.IGNORECASE)
            if m:
                failures.append(f"forbidden phrasing in {name}: {m.group(0)!r} - {why}")

    # House style: no em dashes anywhere in shipped prose. Checked on the raw
    # files, blockquotes included, since style applies to quoted text too.
    for name, text in prose.items():
        if "\u2014" in text:
            n = text.count("\u2014")
            failures.append(f"style: {n} em dash(es) in {name}; use a colon, "
                            "comma or parentheses")

    # Every figure the README embeds must exist, or the landing page ships with
    # broken images.
    for img in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", prose["README.md"]):
        if img.startswith(("http://", "https://")):
            continue  # remote badges are checked by GitHub, not by this guard
        if not (ROOT / img).exists():
            failures.append(f"README embeds a missing figure: {img}")

    n_claims = len(claims())
    if failures:
        print(f"FAILED: {len(failures)} problem(s) across {n_claims} checked claims\n")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {n_claims} claims match the results, "
          f"{len(REQUIRED_HEDGES)} hedges present, "
          f"{len(REQUIRED_DISCLAIMER)} disclaimer phrases intact, "
          f"{len(REQUIRED_PRIOR_ART)} prior-art attributions present, "
          f"{len(FORBIDDEN) + len(FORBIDDEN_NOVELTY)} overclaim patterns absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
