"""Tests that pin each track's headline number, and the claims guard itself.

Every number quoted in README.md or FINDINGS.md appears here with a tolerance
tight enough that a real change in the analysis breaks the build. Loose enough
tolerances would make these tests decorative.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from blinkrate import (track1_investment, track2_weather_split,
                       track3_med_sensitivity, track4_cause_exclusions,
                       track5_undergrounding, track6_ownership, track7_validation)
from blinkrate.shared import ingest

ROOT = Path(__file__).resolve().parents[1]


def _results(name: str) -> dict:
    path = ROOT / "results" / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{name}.json missing; run `python -m blinkrate.run_all`")
    return json.loads(path.read_text())


# --------------------------------------------------------------------------
# track 3, the headline
# --------------------------------------------------------------------------

def test_track3_sensitivity_range():
    s = _results("track3_med_sensitivity")["sensitivity"]
    h = s["headline"]
    assert h["beta_1.5"]["fleet_saidi_without_med"] == pytest.approx(37, abs=1.0)
    assert h["beta_2.5"]["fleet_saidi_without_med"] == pytest.approx(115, abs=1.0)
    assert h["beta_3.0"]["fleet_saidi_without_med"] == pytest.approx(287, abs=1.0)
    assert s["fleet_range_ratio"] == pytest.approx(7.66, abs=0.03)


def test_track3_qualifying_days_is_exact_not_estimated():
    """Expected qualifying days is 365 * (1 - Phi(beta)), independent of sigma.
    If this drifts, the beta grid or the identity has been changed."""
    h = _results("track3_med_sensitivity")["sensitivity"]["headline"]
    assert h["beta_2.5"]["expected_med_days_per_year"] == pytest.approx(2.27, abs=0.01)
    assert h["beta_3.0"]["expected_med_days_per_year"] == pytest.approx(0.49, abs=0.01)


def test_track3_zero_exclusion_mass():
    c = _results("track3_med_sensitivity")["coverage"]
    assert c["share_exactly_zero_exclusion"] == pytest.approx(0.298, abs=0.002)
    assert c["share_admissible"] == pytest.approx(0.672, abs=0.005)
    assert c["n"] == 6245


def test_track3_bunching_survives():
    b = _results("track3_med_sensitivity")["bunching"]
    assert b["excess_mass_ratio"] == pytest.approx(12.0, abs=0.2)
    assert b["ci95"][0] > 1.0, "CI must exclude 1 or the bunching claim is dead"
    assert b["n_clusters"] > 1100
    # 6,245 rows over only ~1,129 distinct utility-states: the panel is deep,
    # not wide, which is exactly why the bootstrap clusters on utility-state
    assert b["n_clusters"] < _results("track3_med_sensitivity")["coverage"]["n"] / 4


def test_track3_standard_choice_gap():
    sc = _results("track3_med_sensitivity")["standard_choice"]
    assert sc["Other"]["median_retained_share"] > sc["IEEE"]["median_retained_share"]
    assert sc["Other"]["median_retained_share"] == pytest.approx(0.883, abs=0.002)
    assert sc["IEEE"]["median_retained_share"] == pytest.approx(0.700, abs=0.002)


def test_track3_bunching_is_deterministic():
    """Same seed, same answer. A bootstrap that wanders makes the CI unciteable."""
    df = ingest.analysis_sample()
    a = track3_med_sensitivity.excess_mass_at_zero_exclusion(df, n_boot=300)
    b = track3_med_sensitivity.excess_mass_at_zero_exclusion(df, n_boot=300)
    assert a["excess_mass_ratio"] == b["excess_mass_ratio"]
    assert a["ci95"] == b["ci95"]


# --------------------------------------------------------------------------
# track 2
# --------------------------------------------------------------------------

def test_track2_excluded_part_carries_the_trend():
    t2 = _results("track2_weather_split")
    assert t2["balanced_panel_utility_states"] == 568
    assert t2["within_utility"]["share_of_change_from_excluded_part"] == pytest.approx(
        0.829, abs=0.005)
    # the headline is a range, not a point; the consecutive window must differ
    assert t2["within_utility_consecutive"]["share_of_change_from_excluded_part"] \
        == pytest.approx(0.880, abs=0.005)


def test_track2_panel_is_balanced():
    """Composition change alone moves the fleet average, so the trend must be
    computed on utilities present in every year."""
    df = track2_weather_split.balanced_panel()
    counts = df.groupby("utility_state")["year"].nunique()
    assert (counts == len(track2_weather_split.ALL_YEARS)).all()
    # after deduplication every year must contribute exactly the same utilities
    assert df.groupby("year").size().nunique() == 1


def test_track2_net_entry_into_exclusion():
    e = _results("track2_weather_split")["exclusion_entry"]
    assert e["started_excluding"] > e["stopped_excluding"]
    assert e["net_entry_into_exclusion"] == pytest.approx(0.086, abs=0.005)
    # and it is a trend across years, not two endpoints
    assert e["trend_pct_points_per_year"] < 0
    assert e["trend_p"] < 0.05


# --------------------------------------------------------------------------
# track 6
# --------------------------------------------------------------------------

def test_track6_ownership_ordering():
    o = _results("track6_ownership")["by_ownership"]
    assert o["IOU"]["median_retained_share"] == pytest.approx(0.643, abs=0.002)
    assert o["Municipal"]["median_retained_share"] == pytest.approx(0.901, abs=0.002)
    assert (o["IOU"]["median_retained_share"] < o["Coop"]["median_retained_share"]
            < o["Municipal"]["median_retained_share"])


def test_track6_retraction_holds():
    """Pins the retraction itself.

    On four filing years the conditional zero-exclusion effect was significant
    at p = 0.026 and was published as a finding. On seven it is not. If a future
    change makes it significant again, FINDINGS' retraction blockquote is wrong
    and has to be rewritten rather than quietly left in place.
    """
    c = _results("track6_ownership")["conditional"]
    raw = abs(c["zero_exclusion_no_size"]["IOU_vs_Coop"])
    conditioned = abs(c["zero_exclusion_with_size"]["IOU_vs_Coop"])
    assert conditioned < raw / 3, "size no longer explains most of the raw gap"
    assert c["zero_exclusion_with_size"]["IOU_p"] > 0.05, (
        "the retracted effect is significant again; rewrite the retraction")
    # what DOES survive conditioning is the intensive margin
    r = c["retained_share_with_size"]
    assert r["IOU_vs_Coop"] < 0
    assert r["IOU_p"] < 0.05
    assert abs(r["IOU_vs_Coop"]) == pytest.approx(0.045, abs=0.004)


# --------------------------------------------------------------------------
# tracks 1, 4, 5, 7
# --------------------------------------------------------------------------

def test_track1_null_is_bounded_not_merely_absent():
    """Q5's null only means something if the design had power and variation."""
    t1 = _results("track1_investment")
    w = t1["within_utility"]
    ami = w["coefficients"]["ami_share"]
    assert ami["beta"] == pytest.approx(0.036, abs=0.004)
    assert ami["ci95"][0] < 0 < ami["ci95"][1], "the null depends on the CI crossing"
    # the identifying variation must actually be there
    assert w["n_moving_ami_gt_0_50"] >= 50
    assert w["n_utility_states"] == 589
    # and the design must have been able to see a moderate effect
    assert ami["mde_80pct_power"] < 0.35

    vd = t1["variance_decomposition"]
    assert vd["share_between_utility"] == pytest.approx(0.587, abs=0.005)
    assert vd["share_between_utility"] + vd["share_within_utility"] == pytest.approx(1)


def test_track1_cross_section_loses_variation_over_time():
    """The reason the first version of this track was wrong, pinned so it cannot
    be reintroduced: AMI share stops varying, so a late cross-section is
    uninformative however it is specified."""
    cs = _results("track1_investment")["cross_sections"]
    assert cs["2016"]["ami_share_iqr"][0] < 0.2
    assert cs["2022"]["ami_share_iqr"][0] > 0.9
    assert cs["2022"]["share_at_100pct"] > cs["2016"]["share_at_100pct"]


def test_track1_designs_agree():
    """Three designs, one answer. If they diverge the writeup is wrong."""
    t1 = _results("track1_investment")
    for res, key in ((t1["within_utility"], "ami_share"),
                     (t1["long_difference"], "d_ami")):
        c = res["coefficients"][key]
        assert c["ci95"][0] < 0 < c["ci95"][1]
    g = t1["long_difference"]["group_comparison"]
    assert abs(g["pct_saidi_difference"]) < 10, "a large group gap would contradict"


def test_track1_states_its_substitution():
    """A substituted question must announce itself in the payload, not only in a
    docstring nobody reads."""
    assert "FERC" in _results("track1_investment")["substitution"]
    assert "deployment" in _results("track1_investment")["substitution"]


def test_track4_is_marked_blocked():
    t4 = _results("track4_cause_exclusions")
    assert t4["status"] == "BLOCKED"
    assert "ferc.gov blocked" in t4["blocker"]
    assert t4["los"]["median_los_retained_share"] == pytest.approx(0.964, abs=0.002)


def test_track5_breakeven_is_far_above_observed():
    t5 = _results("track5_undergrounding")
    be = t5["breakeven"]["case_study_high|cost_central|voll_central"]
    assert be["breakeven_saidi_min_per_yr"] == pytest.approx(1633, abs=2)
    assert be["breakeven_saidi_min_per_yr"] > 8 * t5["observed_median_saidi_with_2022"]
    assert t5["customers_per_mile"]["national_customers_per_mile"] == pytest.approx(
        30.5, abs=0.05)


def test_track5_density_is_what_decides_it():
    """Breakeven scales inversely with customers per mile; the dense end clears
    the median utility's SAIDI, which is the nuance the headline needs."""
    d = _results("track5_undergrounding")["density_sweep"]["case_study_high"]
    dens = d["customers_per_mile"]
    be = d["breakeven_saidi_min_per_yr"]
    assert be[0] > be[-1]
    assert be[-1] * dens[-1] == pytest.approx(be[0] * dens[0], rel=1e-6)
    assert be[-1] < _results("track5_undergrounding")["observed_median_saidi_with_2022"]


def test_track7_source_data_is_internally_consistent():
    c = _results("track7_validation")["caidi_identity"]
    assert c["with_med"]["share_within_tolerance"] == 1.0
    assert c["with_med"]["n_checked"] > 3500, "CAIDI check must span every year"
    assert set(_results("track7_validation")["caidi_identity"]["years_checked"]) == {
        2016, 2017, 2018, 2022}
    assert c["without_med"]["share_within_tolerance"] == 1.0


def test_track7_calibration_beats_closed_form():
    v = _results("track7_validation")["closed_form_vs_procedure"]
    assert v["max_abs_err_calibration"] < 0.03
    assert v["max_abs_err_closed_form"] > 0.15
    assert _results("track7_validation")["round_trip"]["max_abs_error"] < 0.05


# --------------------------------------------------------------------------
# the guard itself
# --------------------------------------------------------------------------

def _run_guard(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "tools" / "check_claims.py")],
                          cwd=cwd, capture_output=True, text=True)


def test_claims_guard_passes_on_the_real_prose():
    r = _run_guard(ROOT)
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("corruption,expect", [
    # a drifted number
    (lambda t: t.replace("7.66x", "9.99x"), "drift"),
    # a deleted hedge
    (lambda t: t.replace("model-implied", "measured"), "hedge missing"),
    # an overclaim
    (lambda t: t.replace("The direction is a property of the rule.",
                         "This proves the rule is arbitrary for all utilities."),
     "forbidden"),
])
def test_claims_guard_catches_corrupted_prose(corruption, expect, tmp_path):
    """The guard is only worth having if it can fail. Feed it a broken copy of
    the real prose and require a non-zero exit."""
    for name in ("README.md", "FINDINGS.md", "FALSIFICATION.md"):
        (tmp_path / name).write_text(corruption((ROOT / name).read_text()))
    (tmp_path / "results").symlink_to(ROOT / "results", target_is_directory=True)

    # the guard resolves paths from its own location, so run a copy rooted here
    src = (ROOT / "tools" / "check_claims.py").read_text()
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "check_claims.py").write_text(src)

    r = subprocess.run([sys.executable, str(tools / "check_claims.py")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 1, f"guard passed corrupted prose:\n{r.stdout}"
    assert expect.split()[0] in r.stdout.lower()


def test_readme_test_count_is_not_stale():
    """The README quotes a test count in its usage block.

    A stale count is a small lie that survives every refactor, so it gets a test
    like any other quoted number. Collection runs in a subprocess so this does
    not recurse.
    """
    import re
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(ROOT / "tests")],
        cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", r.stdout)
    assert m, f"could not parse collection output:\n{r.stdout[-500:]}"
    collected = int(m.group(1))

    readme = (ROOT / "README.md").read_text()
    stated = re.search(r"pytest\s+#\s*(\d+) tests", readme)
    assert stated, "README usage block no longer states a test count"
    assert int(stated.group(1)) == collected, (
        f"README says {stated.group(1)} tests, collection finds {collected}")


def test_track3_ranking_sensitivity():
    """The exclusion reorders the leaderboard, in every filing year."""
    rk = _results("track3_med_sensitivity")["ranking"]
    assert set(rk["by_year"]) == {"2013", "2014", "2015", "2016", "2017",
                                 "2018", "2022"}
    y = rk["by_year"]["2022"]
    assert y["spearman"] == pytest.approx(0.655, abs=0.003)
    assert y["pct_changing_quartile"] == pytest.approx(52.4, abs=1.0)
    assert y["median_rank_move"] == pytest.approx(18.5, abs=0.5)
    # present in all seven years, not a 2022 artefact
    assert max(v["spearman"] for v in rk["by_year"].values()) < 0.8
    assert min(v["pct_changing_quartile"] for v in rk["by_year"].values()) > 35


def test_track3_ranking_note_refuses_the_manipulation_reading():
    """The finding is about incommensurable series, not misconduct. If the
    disclaimer is dropped from the payload, the result reads as an accusation."""
    note = _results("track3_med_sensitivity")["ranking"]["note"]
    assert "not evidence of anything improper" in note
    assert "hurricane" in note


def test_utility_profile_cli_runs():
    """The per-utility tool is a deliverable, so it gets a smoke test."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "utility_profile.py"),
         "--id", "14715"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WHAT WOULD HAVE BEEN FILED AT OTHER THRESHOLDS" in r.stdout
    assert "model-implied" in r.stdout, "the caveat must print with the numbers"


def test_utility_profile_refuses_ambiguous_match():
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "utility_profile.py"),
         "--name", "Power"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1
    assert "more than one utility-state" in r.stdout


def test_track2_hurricane_placebo_is_a_placebo():
    """The geographic weather test only means something as a placebo.

    The state list is fixed from the 2017 storm tracks and applied to every
    transition. If those states moved most in some other year the list would
    just be picking up storm-prone states generally, and the inference dies.
    """
    geo = _results("track2_weather_split")["spike_geography"]
    assert geo["largest_excluded_gap_transition"] == "2016_2017"
    # 2017 must stand clear of the runner-up, not edge past it
    assert geo["largest_excluded_gap_minutes"] > 2 * geo[
        "second_largest_excluded_gap_minutes"]

    t = geo["by_transition"]["2016_2017"]
    assert t["d_excluded_hurricane_cw"] > 5 * t["d_excluded_other_cw"]
    # and the everyday series in those same states must NOT move, or the spike
    # is not specific to the excluded portion
    assert abs(t["d_everyday_hurricane_cw"]) < 5
    # the following year it gives the minutes back
    assert _results("track2_weather_split")["spike_geography"][
        "by_transition"]["2017_2018"]["d_excluded_hurricane_cw"] < -400

    # the list must not simply be the biggest states
    assert geo["hurricane_states_share_of_panel_customers_pct"] < 35


def test_track2_separates_trend_from_spike():
    """Q4's whole claim is that the two series behave differently in kind: the
    everyday one trends, the excluded one spikes."""
    st = _results("track2_weather_split")["gradual_or_step"]
    assert st["without_med_slope_p"] < 0.01
    assert st["without_med_r2"] > 0.8
    assert st["gap_slope_p"] > 0.05, "if the gap trends cleanly, Q4 is rewritten"
    assert st["gap_r2"] < st["without_med_r2"]


def test_track8_leave_one_state_out_only_bites_q4():
    """A7, pinned. Three headlines must be state-robust and one must not be.

    If a future change makes Q4's share state-robust, the rewrite that separates
    a national trend from a Gulf-coast aggregate is wrong. If it makes any of the
    other three state-dependent, they need the same treatment.
    """
    a7 = _results("track8_falsification")["A7_leave_one_state_out"]
    assert a7["n_states_dropped"] > 45
    robust = ["fleet_range_ratio", "excess_mass", "pct_changing_quartile_2022"]
    for key in robust:
        assert a7["summary"][key]["max_pct_shift"] < 10, (
            f"{key} became state-dependent and needs scoping like Q4")
    fragile = a7["summary"]["share_from_excluded"]
    assert fragile["most_influential_state"] == "FL"
    assert fragile["max_pct_shift"] > 30
    assert a7["florida"]["share_from_excluded"] == pytest.approx(0.509, abs=0.005)


def test_track2_storm_states_separate_trend_from_aggregate():
    """The diagnosis behind Q4's rewrite: a customer-weighting effect, not an
    absent pattern. The unweighted share must survive where the weighted one
    does not, or the explanation in FINDINGS is wrong."""
    ss = _results("track2_weather_split")["storm_state_sensitivity"]
    a, b = ss["all_states"], ss["hurricane_states_dropped"]
    assert b["share_from_excluded_cw"] < 0.5 < a["share_from_excluded_cw"]
    assert b["share_from_excluded_unweighted"] > 0.7
    assert ss["reading"]["excluded_share_survives"] is False
    # the trend, by contrast, must barely move
    assert ss["reading"]["everyday_trend_survives"] is True
    assert abs(b["everyday_slope"] - a["everyday_slope"]) < 0.6
    assert b["everyday_p"] < 0.01
