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
import numpy as np
import pandas as pd
from scipy import stats

from blinkrate import (track1_investment, track2_weather_split,
                       track3_med_sensitivity, track4_cause_exclusions,
                       track5_undergrounding, track6_ownership, track7_validation)
from blinkrate.shared import ingest
from blinkrate.shared import io as results_io

ROOT = Path(__file__).resolve().parents[1]

# Rounding to SIG_FIGS significant figures moves a value by at most
# 5 * 10**-SIG_FIGS relative, so a test comparing a stored result with an exact
# value allows twice that.
STORED_REL = 10.0 ** (1 - results_io.SIG_FIGS)

def _guard_prose_files() -> tuple[str, ...]:
    """The prose list, read from the guard itself.

    Tests used to keep their own copy of this list, and it fell out of step with
    the guard twice (once when LITERATURE.md was added, once for CHANGELOG.md),
    failing every corruption test for the wrong reason. Single source of truth.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_claims", ROOT / "tools" / "check_claims.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return tuple(mod.PROSE)


PROSE_FILES = _guard_prose_files()


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
    for name in PROSE_FILES:
        (tmp_path / name).write_text(corruption((ROOT / name).read_text()))
    (tmp_path / "results").symlink_to(ROOT / "results", target_is_directory=True)
    (tmp_path / "blinkrate").symlink_to(ROOT / "blinkrate", target_is_directory=True)

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


def test_readme_claim_count_is_not_stale():
    """The README says how many quoted figures the guard checks. It still said
    74, the count when the sentence was written, after the guard had grown to
    105 across three releases: the kind of stale number the guard exists to
    catch. So the count is read from the guard itself."""
    import importlib.util
    import re
    spec = importlib.util.spec_from_file_location(
        "check_claims", ROOT / "tools" / "check_claims.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stated = re.search(r"check_claims\.py` pairs (\d+) figures",
                       (ROOT / "README.md").read_text())
    assert stated, "README no longer states how many figures the guard checks"
    assert int(stated.group(1)) == len(mod.claims()), (
        f"README says {stated.group(1)}, the guard checks {len(mod.claims())}")


def test_verify_script_replays_every_ci_step():
    """UPLOAD.md tells a reader that ./verify.sh is CI run locally, so every
    check CI makes must be in it. Its first install step also failed on Python
    3.12 and later until v1.2.0: it installs without build isolation, and venvs
    there ship without setuptools, so the backend must be installed first."""
    import re
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    verify = (ROOT / "verify.sh").read_text()
    for step in ("blinkrate.shared.finite_sample --check", "blinkrate.run_all",
                 "git diff --exit-code", "-- results/", "pytest -q",
                 "tools/check_claims.py"):
        assert step in ci, f"CI no longer runs {step!r}; update this test"
        assert step in verify, f"verify.sh skips a CI step: {step!r}"
    backend = re.search(r'pip" install[^\n]*setuptools', verify)
    no_isolation = verify.index("--no-build-isolation")
    assert backend and backend.start() < no_isolation, (
        "verify.sh must install setuptools before installing without isolation")


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
         "--id", "4110"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WHAT WOULD HAVE BEEN FILED AT OTHER THRESHOLDS" in r.stdout
    assert "model-implied" in r.stdout, "the caveat must print with the numbers"


def test_seed_spread_compares_claims_by_position():
    """tools/seed_spread.py takes minutes per seed, so the suite checks only its
    comparison: identical results report nothing, and a figure moved past the
    guard's tolerance is reported as such."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "seed_spread", ROOT / "tools" / "seed_spread.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    base = mod.claim_values(ROOT / "results")
    assert mod.compare(base, [base]) == []
    moved = [(t, v + 2 * tol + 1.0, tol) for t, v, tol in base]
    rows = mod.compare(base, [moved])
    assert len(rows) == len(base) and all(r["exceeds_tolerance"] for r in rows)


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


def test_track9_aggregator_spread():
    """Q8: the averaging rule alone moves the national number."""
    d = _results("track9_aggregation")
    y = d["by_year"]["2022"]
    assert y["with_med_spread_x"] == pytest.approx(2.07, abs=0.02)
    assert y["without_med_spread_x"] == pytest.approx(1.44, abs=0.02)
    # ordering must hold: the customer-weighted mean is tail-exposed, the
    # median utility is not, so the gap between them is the whole point
    assert y["with_med"]["customer_weighted_mean"] > y["with_med"]["median_utility"]
    assert y["with_med"]["unweighted_mean"] > y["with_med"]["customer_weighted_median"]


def test_track9_combined_space_exceeds_either_choice_alone():
    """Threshold and aggregator compound. If the combined range ever collapses to
    the threshold range alone, Q8's framing is wrong."""
    d = _results("track9_aggregation")
    combined = d["combined_space"]["range_x"]
    threshold_only = _results("track3_med_sensitivity")["sensitivity"][
        "fleet_range_ratio"]
    assert combined > threshold_only
    assert combined == pytest.approx(14.32, abs=0.1)
    assert d["combined_space"]["standard_choice"] == pytest.approx(129.7, abs=0.3)


def test_track9_national_total_is_concentrated():
    c = _results("track9_aggregation")["concentration"]["2022"]
    assert c["with_med"]["top_10_share"] > 0.3
    assert c["with_med_gini"] > 0.8


def test_track9_scopes_q4_trend_honestly():
    """Q4's trend is directionally robust to the aggregator but not uniformly
    significant. If a change makes all six significant, Q4's hedge is too weak
    and should be strengthened; if any slope goes negative, Q4 is wrong."""
    t = _results("track9_aggregation")["trend_by_aggregator"]
    assert t["all_positive"] is True
    assert t["all_significant_at_05"] is False
    n_sig = sum(1 for v in t["fits"].values() if v["p"] < 0.05)
    assert n_sig == 4
    assert t["slope_range"][0] > 1.0


def test_claims_guard_catches_an_overclaiming_figure_title():
    """Figure titles are prose the reader sees.

    A track 9 title once asserted the trend slope did not depend on the
    aggregation rule, which that track's own numbers contradict. Nothing checked
    figure text at the time. This proves the check now exists by planting an
    overclaim in a temporary copy of the package.
    """
    import shutil
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(ROOT / "blinkrate", tmp / "blinkrate")
        for name in PROSE_FILES:
            shutil.copy(ROOT / name, tmp / name)
        (tmp / "results").symlink_to(ROOT / "results", target_is_directory=True)
        (tmp / "tools").mkdir()
        shutil.copy(ROOT / "tools" / "check_claims.py", tmp / "tools")

        target = tmp / "blinkrate" / "track9_aggregation.py"
        body = target.read_text()
        marker = 'ax2.set_title("Every rule slopes up. How steeply is another matter.",'
        assert marker in body, "figure title moved; update this test"
        target.write_text(body.replace(
            marker, 'ax2.set_title("This proves the rule is irrelevant",'))

        r = subprocess.run([sys.executable, str(tmp / "tools" / "check_claims.py")],
                           cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 1, f"guard passed an overclaiming title:\n{r.stdout}"
        assert "figure" in r.stdout.lower()


@pytest.mark.parametrize("corruption,expect", [
    (lambda t: t.replace("Independent personal project", "Personal project"),
     "disclaimer"),
    (lambda t: t.replace("corroboration", "a discovery"), "prior-art"),
    (lambda t: t.replace("national-scale", "a novel"), "novelty"),
])
def test_claims_guard_protects_disclaimer_and_prior_art(corruption, expect,
                                                        tmp_path):
    """The independence disclaimer and the prior-art framing are load-bearing.

    Deleting either turns a true statement into a false one and nothing else in
    the build would notice, so the guard has to fail on both.
    """
    for name in PROSE_FILES:
        (tmp_path / name).write_text(corruption((ROOT / name).read_text()))
    (tmp_path / "results").symlink_to(ROOT / "results", target_is_directory=True)
    (tmp_path / "blinkrate").symlink_to(ROOT / "blinkrate", target_is_directory=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "check_claims.py").write_text(
        (ROOT / "tools" / "check_claims.py").read_text())

    r = subprocess.run([sys.executable, str(tmp_path / "tools" / "check_claims.py")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 1, f"guard passed corrupted prose:\n{r.stdout}"
    assert expect in r.stdout.lower()


def test_employer_is_not_a_worked_example():
    """A repository that disclaims employer affiliation must not use that
    employer as its headline example. Caught in a sibling repo where the
    employer was named five times in exactly that position."""
    import re
    for name in PROSE_FILES:
        # "ppl" is a substring of "supply", so match the name with word
        # boundaries rather than counting letters. The first version of this
        # test counted substrings and failed on the word "supply".
        hits = len(re.findall(r"\bPPL\b", (ROOT / name).read_text()))
        if name == "README.md":
            assert hits == 1, "PPL should appear only in the independence disclaimer"
        else:
            assert hits == 0, f"{name} names the employer"


def test_employer_is_not_a_worked_example_in_code_either():
    """The same rule for code. Until v1.2.0 the profile tool's usage examples,
    which print with --help, opened with the employer by name and by EIA id,
    and the tool's smoke test ran on that id; the prose test above reads
    neither. The id is looked up from the vendored data rather than written
    here, so this file can scan itself."""
    import re
    df = ingest.analysis_sample()
    ids = {str(int(i)) for i in df.loc[
        df["utility_name"].str.contains(r"\bPPL\b", regex=True), "utility_id"]}
    assert ids, "no employer id found, so the scan below would pass vacuously"
    code = [p for p in (ROOT / "tools").glob("*.py") if p.name != "check_claims.py"]
    code += sorted((ROOT / "blinkrate").rglob("*.py"))
    code += sorted((ROOT / "tests").glob("*.py"))
    for path in code:
        text = path.read_text()
        for i in ids:
            assert not re.search(rf"\b{i}\b", text), f"{path.name} uses the id {i}"
        if path.parent.name != "tests":  # tests name it in their own messages
            assert not re.search(r"\bPPL\b", text), f"{path.name} names the employer"


def test_stated_falsification_criterion_is_actually_run():
    """FINDINGS commits to a criterion. A criterion nobody runs is decoration.

    Asserts the attack exists, reports both halves, and that the repository
    still passes its own test. If a future change makes either half fail, the
    central claim in README and FINDINGS is overstated and has to be rewritten
    rather than left standing.
    """
    a8 = _results("track8_falsification")["A8_stated_falsification_criterion"]
    p1 = a8["part1_rule_vs_cross_utility_spread"]
    p2 = a8["part2_reversal_within_exposure"]

    assert p1["rule_exceeds_p10_p90_spread"] is True
    assert p1["own_sweep_median_x"] == pytest.approx(6.18, abs=0.05)
    assert p1["cross_utility_spread_x"]["p90_over_p10"] == pytest.approx(
        3.92, abs=0.05)
    assert p1["ratio_rule_to_spread"] > 1.0

    assert p2["survives"] is True
    assert p2["min_within_stratum"] > 0.6 * p2["pooled_pct_changing_quartile"]
    for key in ("low_pre_exposure", "mid_pre_exposure", "high_pre_exposure",
                "non_hurricane_states"):
        assert p2["by_stratum"][key] is not None
        assert p2["by_stratum"][key]["pct_changing_quartile"] > 35

    assert a8["criterion_met"] is True


def test_exposure_stratifier_is_out_of_sample():
    """Part two only means something if the stratifier is not the outcome.

    Exposure is the mean exclusion share over 2013-2018, applied to 2022. If a
    future change stratifies on the same year being tested the result becomes
    circular, and this test is the only thing that would catch it.
    """
    src = (ROOT / "blinkrate" / "track8_falsification.py").read_text()
    block = src[src.index("def a8_stated_falsification_criterion"):
                src.index("def a9_leave_one_utility_out")]
    assert 'df["year"].between(2013, 2018)' in block
    assert "pre_exposure" in block


def test_q8_spread_survives_leave_one_utility_out():
    """A9: Q8's finding is about the gap between aggregation rules, which must
    not be a single-utility artefact even though the level plainly is."""
    a9 = _results("track8_falsification")["A9_leave_one_utility_out"]
    assert a9["spread_survives_dropping_top_1"] is True
    assert a9["spread_survives_dropping_top_10"] is True
    drops = a9["by_drop"]
    assert drops["drop_top_10"]["spread_x"] == pytest.approx(2.00, abs=0.05)
    # the level falls sharply while the spread holds; that contrast is the point
    assert (drops["drop_top_10"]["customer_weighted_mean"]
            < 0.8 * drops["drop_top_0"]["customer_weighted_mean"])
    assert a9["largest_contributor"]["share_of_national_customer_minutes"] > 0.1


def test_a10_breaking_point_is_pinned():
    """A10: the central comparison is conditional on daily outage tails.

    If a future change makes the claim hold under heavy tails, the rescope in
    README and FINDINGS is too cautious and should be revisited. If it makes the
    claim fail even under log-normality, the repository has no headline
    comparison left and the README needs rewriting, not a tweak.
    """
    a10 = _results("track8_falsification")["A10_tail_breaking_point"]
    bt = a10["by_tail"]
    assert bt["lognormal"]["claim_holds"] is True
    assert bt["t_nu30"]["claim_holds"] is True
    assert bt["t_nu15"]["claim_holds"] is False
    assert a10["breaking_point_nu_between"] == [15.0, 30.0]
    # monotone: heavier tails always shrink the sweep
    order = ["lognormal", "t_nu30", "t_nu15", "t_nu10", "t_nu7", "t_nu5", "t_nu3"]
    sweeps = [bt[k]["median_own_sweep_x"] for k in order]
    assert all(a > b for a, b in zip(sweeps, sweeps[1:]))
    # the spread compared against is observed data, identical across tails
    assert a10["cross_utility_spread_p90_p10"] == pytest.approx(3.92, abs=0.02)


def test_a10_lognormal_row_reproduces_a8():
    """A10 rebuilds its own surfaces at lower resolution. Its log-normal row must
    reproduce A8's figure closely, or the breaking point is measured on a
    different instrument than the claim it breaks."""
    t8 = _results("track8_falsification")
    a8 = t8["A8_stated_falsification_criterion"]["part1_rule_vs_cross_utility_spread"]
    a10 = t8["A10_tail_breaking_point"]["by_tail"]["lognormal"]
    assert a10["median_own_sweep_x"] == pytest.approx(a8["own_sweep_median_x"],
                                                       rel=0.05)


def test_unconditional_headline_cannot_return():
    """The rescoped sentence may only appear as a quoted, superseded claim."""
    import re
    for name in PROSE_FILES:
        text = (ROOT / name).read_text()
        unquoted = re.sub(r"^>.*$", "", text, flags=re.MULTILINE)
        assert not re.search(r"more than the whole\s+industry spans", unquoted), (
            f"{name} states the A10-rescoped headline without its condition")


def _guard_on(tmp_path, edit: dict) -> subprocess.CompletedProcess:
    """Run the guard against a copy of the prose with `edit` applied.

    `edit` maps a prose file name to a function transforming its text.
    """
    for name in PROSE_FILES:
        text = (ROOT / name).read_text()
        (tmp_path / name).write_text(edit.get(name, lambda t: t)(text))
    (tmp_path / "results").symlink_to(ROOT / "results", target_is_directory=True)
    (tmp_path / "blinkrate").symlink_to(ROOT / "blinkrate", target_is_directory=True)
    (tmp_path / "figures").symlink_to(ROOT / "figures", target_is_directory=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "check_claims.py").write_text(
        (ROOT / "tools" / "check_claims.py").read_text())
    return subprocess.run([sys.executable, str(tmp_path / "tools" / "check_claims.py")],
                          cwd=tmp_path, capture_output=True, text=True)


def test_guard_catches_a_stale_second_copy(tmp_path):
    """A figure quoted in two files must be right in both.

    The guard used to pass as soon as the exact claim appeared anywhere, so a
    stale copy in a second file survived indefinitely. Corrupt only the
    FALSIFICATION copy of a number FINDINGS also quotes, and require a failure.
    """
    import re
    findings = re.sub(r"\s+", " ", re.sub(r"^>\s?", "", (
        ROOT / "FINDINGS.md").read_text(), flags=re.MULTILINE))
    # FINDINGS wraps this figure across a line inside a blockquote, so check it
    # the way the guard reads prose: blockquote markers stripped, whitespace
    # collapsed.
    assert "3.6 points at p = 0.199" in findings
    assert "3.6 points at p = 0.199" in (ROOT / "FALSIFICATION.md").read_text()
    r = _guard_on(tmp_path, {"FALSIFICATION.md": lambda t: t.replace(
        "3.6 points at p = 0.199", "4.1 points at p = 0.199")})
    assert r.returncode == 1, r.stdout
    assert "stale copy" in r.stdout


def test_guard_enforces_no_em_dashes(tmp_path):
    r = _guard_on(tmp_path, {"README.md": lambda t: t.replace(
        "Short answer.", "Short answer \u2014 in brief.", 1)})
    assert r.returncode == 1, r.stdout
    assert "em dash" in r.stdout


def test_stored_results_are_rounded_for_reproducibility():
    """Results are rounded to 9 significant figures so they are byte-identical
    across library versions and runner CPUs; CI's git diff on results/ depends
    on it. The p-value pair is real: track 6's log_customers_p as computed with
    the Intel AVX-512 and AMD Zen 3 kernels. At the 12 figures stored before
    v1.2.0 the two disagreed in the last digit and CI failed on Zen 3."""
    from blinkrate.shared import io
    assert io.SIG_FIGS == 9
    intel, zen3 = 8.589131538277231e-14, 8.58913153832389e-14  # numpy 2.5.4
    assert f"{intel:.12g}" != f"{zen3:.12g}"
    assert io._round_floats(intel) == io._round_floats(zen3)
    assert io._round_floats(0.12935628322404175) == io._round_floats(
        0.12935628322404166)
    assert io._round_floats({"x": [1.0, float("nan")]}) == {"x": [1.0, None]}


def test_guard_rejects_long_quotations(tmp_path):
    """Quotations from sources stay under 15 words. Paraphrase the rest."""
    planted = ('The report found that "no alternative method reduced variability '
               'for every utility in the sample and several made matters worse '
               'for many of them over time."')
    r = _guard_on(tmp_path, {"LITERATURE.md": lambda t: t + "\n\n" + planted + "\n"})
    assert r.returncode == 1, r.stdout
    assert "quotation of" in r.stdout


def test_guard_allows_long_paper_titles(tmp_path):
    title = ('"Tracking the Reliability of the U.S. Electric Power System: An '
             'Assessment of Publicly Available Information Reported to State '
             'Public Utility Commissions"')
    r = _guard_on(tmp_path, {"LITERATURE.md": lambda t: t + "\n\nSee " + title + ".\n"})
    assert "quotation of" not in r.stdout, r.stdout


def test_profile_any_pair_with_tails():
    """--pair works for utilities outside the panel, and --tails shows the
    sweep shrinking as tails get heavier while the filed value is reproduced."""
    import re
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "utility_profile.py"),
                        "--pair", "200", "120", "--tails"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    sweeps = [float(x) for x in re.findall(r"([\d.]+)x\s*$", r.stdout, re.MULTILINE)]
    assert len(sweeps) == 4
    assert all(a > b for a, b in zip(sweeps, sweeps[1:])), sweeps
    # every row reproduces the filed without-MED value at beta 2.5
    assert r.stdout.count("120.0") >= 4
    assert "attack A10" in r.stdout


def test_profile_pair_outside_the_model_is_reported_not_crashed():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "utility_profile.py"),
                        "--pair", "120", "120"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "outside what IEEE 1366's own log-normal model can" in r.stdout


def test_a11_window_is_a_second_condition():
    """A11: the headline comparison also depends on the threshold window.

    Under log-normal tails it holds only at about +/-0.75 or wider, and at +/-0.5
    it fails under every tail tested. If a future change makes it hold at +/-0.5,
    the README's "two analyst choices" framing is too cautious and should be
    loosened; if it stops holding anywhere, the claim should be withdrawn.
    """
    a11 = _results("track8_falsification")["A11_threshold_window"]
    be = a11["break_even_half_width"]
    assert be["lognormal"] == pytest.approx(0.75, abs=0.03)
    for tail, row in a11["grid"].items():
        assert row["h_0.5"]["claim_holds"] is False, (
            f"claim now holds at +/-0.5 under {tail}; rescope README")
    assert a11["grid"]["lognormal"]["h_1.0"]["claim_holds"] is True


def test_a11_heavier_tails_need_wider_windows():
    """The break-even half-width must widen as tails get heavier. If it does not,
    the surfaces are wrong, because heavy tails shrink the sweep at any window."""
    be = _results("track8_falsification")["A11_threshold_window"][
        "break_even_half_width"]
    chain = [be["lognormal"], be["t_nu60"], be["t_nu30"], be["t_nu15"]]
    assert all(x is not None for x in chain)
    assert chain == sorted(chain), f"break-even not monotone in tail weight: {chain}"
    assert be["t_nu7"] is None, "nu=7 should fail at every window up to +/-1.0"


def test_a11_major_event_days_are_the_standards_own_arithmetic():
    """Windows are expressed in major event days per year so a reader can judge
    them on IEEE's working-group criterion. The conversion must be exactly the
    standard's fitted-model rate, 365 * (1 - Phi(beta)), or the units lie."""
    m = _results("track8_falsification")["A11_threshold_window"]["med_days_per_year"]
    for key, beta in (("at_standard_2.5", 2.5), ("at_2.0", 2.0), ("at_1.75", 1.75),
                      ("at_3.0", 3.0)):
        assert m[key] == pytest.approx(365 * (1 - stats.norm.cdf(beta)),
                                       rel=STORED_REL)
    low = _results("track8_falsification")["A11_threshold_window"][
        "lognormal_break_even_med_days_low_edge"]
    assert 13 < low < 17, "the break-even low edge should sit near 15 days a year"


def test_a11_reuses_a10_surfaces():
    """A11 and A10 must be directly comparable, which means one surface builder."""
    src = (ROOT / "blinkrate" / "track8_falsification.py").read_text()
    block = src[src.index("def a11_threshold_window"):]
    block = block[:block.index("\ndef ")]
    assert "_tail_surface(" in block


# --------------------------------------------------------------------------
# provenance: filed data and model-implied separated at the schema level
# --------------------------------------------------------------------------

def test_every_result_declares_its_provenance():
    """Every results file carries a _provenance block covering exactly its keys."""
    import glob
    from blinkrate.shared import provenance as pv
    files = sorted(glob.glob(str(ROOT / "results" / "*.json")))
    assert len(files) == len(pv.REGISTRY)
    for f in files:
        d = json.loads(Path(f).read_text())
        assert "_provenance" in d, f"{f} has no provenance block"
        declared = set(d["_provenance"]["blocks"])
        produced = {k for k in d if not k.startswith("_")}
        assert declared == produced, f"{Path(f).name}: {declared ^ produced}"
        for block in d["_provenance"]["blocks"].values():
            assert block["default"] in pv.KINDS
            assert all(k in pv.KINDS for k in block["exceptions"].values())


def test_undeclared_result_cannot_be_saved():
    """The point of schema-level separation: a new number cannot be published
    without someone deciding whether it is filed data or model-implied."""
    from blinkrate.shared import provenance as pv
    good = {k: 0 for k in pv.REGISTRY["track9_aggregation"]}
    pv.stamp("track9_aggregation", good)
    with pytest.raises(pv.ProvenanceError, match="not declared"):
        pv.stamp("track9_aggregation", {**good, "a_new_headline": 1.0})
    with pytest.raises(pv.ProvenanceError, match="no longer"):
        pv.stamp("track9_aggregation",
                 {k: 0 for k in list(good)[:-1]})
    with pytest.raises(pv.ProvenanceError, match="no provenance registry"):
        pv.stamp("track99_unregistered", {})


@pytest.mark.parametrize("file,block,field,expected", [
    # Q1: the threshold sweep is model-implied
    ("track3_med_sensitivity", "sensitivity", None, "model_implied"),
    # Q2: the mass point is filed data, the admissibility share is not
    ("track3_med_sensitivity", "coverage", "share_exactly_zero_exclusion", "filed_data"),
    ("track3_med_sensitivity", "coverage", "share_admissible", "model_implied"),
    ("track3_med_sensitivity", "bunching", None, "filed_data"),
    # Q3: rank reversal between two published series is filed data
    ("track3_med_sensitivity", "ranking", None, "filed_data"),
    # Q4: the everyday trend and the placebo are filed data
    ("track2_weather_split", "gradual_or_step", None, "filed_data"),
    ("track2_weather_split", "spike_geography", None, "filed_data"),
    # Q8: the 2.07x spread is filed data, the 14.32x combined space is not
    ("track9_aggregation", "by_year", None, "filed_data"),
    ("track9_aggregation", "combined_space", None, "model_implied"),
    # A8: part one inherits the model, part two does not
    ("track8_falsification", "A8_stated_falsification_criterion",
     "part1_rule_vs_cross_utility_spread", "model_implied"),
    ("track8_falsification", "A8_stated_falsification_criterion",
     "part2_reversal_within_exposure", "filed_data"),
    ("track8_falsification", "A11_threshold_window", None, "model_implied"),
])
def test_schema_matches_the_prose_basis_labels(file, block, field, expected):
    """FINDINGS labels each answer "Basis: filed data" or "Basis: model-implied".
    The schema must say the same thing, or one of them is lying."""
    from blinkrate.shared import provenance as pv
    assert pv.kind_of(file, block, field) == expected


def test_what_holds_regardless_is_all_filed_data():
    """README lists what survives regardless of the log-normal assumption. Each
    item must be filed data in the schema; a model-implied quantity in that list
    would be exactly the overclaim the list exists to prevent."""
    from blinkrate.shared import provenance as pv
    readme = (ROOT / "README.md").read_text()
    assert "What holds regardless" in readme
    regardless = [
        ("track3_med_sensitivity", "coverage", "share_exactly_zero_exclusion"),
        ("track3_med_sensitivity", "ranking", None),
        ("track2_weather_split", "gradual_or_step", None),
        ("track9_aggregation", "by_year", None),
    ]
    for file, block, field in regardless:
        assert pv.kind_of(file, block, field) == "filed_data", (file, block, field)


_NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen".split())}


def test_attack_count_is_not_stale_anywhere_it_is_published():
    """The attack count is stated in the README and in the Zenodo metadata that
    is archived permanently on release. It went stale twice ("seven attacks" in
    the layout block survived four more attacks), so it is derived from the
    results rather than trusted to memory."""
    import re
    n_attacks = sum(1 for k in _results("track8_falsification")
                    if re.match(r"A\d+_", k)
                    and not re.match(r"A1b_", k))
    readme = (ROOT / "README.md").read_text()
    zenodo = json.loads((ROOT / ".zenodo.json").read_text())["description"]
    word = {v: k for k, v in _NUMBER_WORDS.items()}[n_attacks]
    assert f"{word} attacks on the above" in readme
    # whitespace-tolerant: prose reflows, and a line break inside the phrase
    # must not make a correct count look stale
    assert re.search(rf"\b\w+\s+of\s+{word}\s+attacks\s+landed", readme,
                     re.IGNORECASE)
    assert f"{word} adversarial attacks" in zenodo
    upload = (ROOT / "UPLOAD.md").read_text()
    assert f"{word} adversarial attacks" in upload
    for stale in (w for w, i in _NUMBER_WORDS.items() if i != n_attacks):
        assert f"{stale} adversarial attacks" not in zenodo, f"zenodo says {stale}"
        assert f"{stale} adversarial attacks" not in upload, f"UPLOAD says {stale}"


def test_release_version_is_consistent():
    """pyproject, CITATION.cff, .zenodo.json and the newest CHANGELOG heading
    must agree, or the archived release cites a version the code does not have."""
    import re
    py = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(),
                   re.MULTILINE).group(1)
    cff = re.search(r"^version: (\S+)", (ROOT / "CITATION.cff").read_text(),
                    re.MULTILINE).group(1)
    zen = json.loads((ROOT / ".zenodo.json").read_text()).get("version", py)
    log = re.search(r"^## v(\S+)", (ROOT / "CHANGELOG.md").read_text(),
                    re.MULTILINE).group(1)
    assert py == cff == zen == log, (py, cff, zen, log)


# --------------------------------------------------------------------------
# second literature pass: A12, A13, the zero-exclusion benchmark, the tail tool
# --------------------------------------------------------------------------

def test_a13_headline_fails_on_every_evidence_window_under_every_tail():
    """The decisive result. On threshold windows the literature supports, the
    model-implied central comparison fails even under IEEE 1366's own
    log-normal assumption. If it ever holds on one of these windows, the
    withdrawal in FINDINGS is wrong and has to be reversed, not kept."""
    a13 = _results("track8_falsification")["A13_evidence_grounded_window"]
    assert a13["holds_anywhere"] is False
    assert a13["best_ratio_anywhere"] == pytest.approx(0.86, abs=0.02)
    for tail in ("lognormal", "laplace", "t_nu15"):
        for window in a13["grid"][tail].values():
            assert window["claim_holds"] is False


def test_a13_windows_come_from_the_standards_own_arithmetic():
    """Each window edge is the beta at which 365 * (1 - Phi(beta)) equals the
    evidence-backed frequency. If the conversion drifts, the windows stop
    meaning what LITERATURE.md says they mean."""
    a13 = _results("track8_falsification")["A13_evidence_grounded_window"]
    for name, (lo_rate, hi_rate) in a13["windows_in_med_days_per_year"].items():
        lo_beta, hi_beta = a13["windows_in_beta"][name]
        assert 365 * stats.norm.sf(lo_beta) == pytest.approx(hi_rate, rel=1e-3)
        assert 365 * stats.norm.sf(hi_beta) == pytest.approx(lo_rate, rel=1e-3)


def test_a13_fleet_magnitude_on_evidence_window():
    """Q1's 7.66x sweeps beta 1.5 to 3.5 under log-normal tails. On the widest
    window the evidence supports it is far smaller, and smaller again under
    heavier tails, which is the ordering FINDINGS reports."""
    f = _results("track8_falsification")["A13_evidence_grounded_window"][
        "fleet_range_on_widest_evidence_window"]
    assert f["lognormal"]["range_x"] == pytest.approx(3.16, abs=0.03)
    assert f["laplace"]["range_x"] == pytest.approx(1.52, abs=0.03)
    assert (f["laplace"]["range_x"] < f["t_nu15"]["range_x"]
            < f["lognormal"]["range_x"])


def test_a12_laplace_fails_at_every_window():
    a12 = _results("track8_falsification")["A12_pareto_tail"]
    assert a12["holds_at_any_window"] is False
    assert max(v["ratio_to_spread"] for v in a12["by_window"].values()) < 0.6


def test_a12_tail_mass_ordering_is_stated_correctly():
    """Laplace is asymptotically lighter than any Student-t, but only beyond
    roughly 40 standard deviations. At the standard's 2.5 it carries more mass
    than t with 15 df, which is why it fails harder. The implied major event
    days per year are the checkable form of that claim."""
    m = _results("track8_falsification")["A12_pareto_tail"]["med_days_per_year_at_2_5"]
    assert m["lognormal"] == pytest.approx(2.27, abs=0.01)
    assert m["laplace"] == pytest.approx(5.32, abs=0.01)
    assert m["lognormal"] < m["t_nu30"] < m["t_nu15"] < m["laplace"]
    lo, hi = _results("track8_falsification")["A12_pareto_tail"][
        "working_group_observed_range"]
    assert lo <= m["laplace"] <= hi


def test_zero_exclusion_benchmark_rescopes_q2():
    """Large IEEE filers sit inside the range genuine segmentation produces;
    the mass point lives with smaller and self-defined-standard filers."""
    z = _results("track3_med_sensitivity")["zero_exclusion_benchmark"]
    b = z["benchmarks"]
    assert b["nominal_2_27_per_year"] == pytest.approx(
        (1 - stats.norm.sf(2.5)) ** 365, rel=STORED_REL)
    assert z["generous_ceiling"] == pytest.approx(np.exp(-2.0), rel=STORED_REL)
    ieee = z["by_standard_and_size"]["IEEE"]
    assert z["large_ieee_within_benchmark_range"] is True
    assert ieee["100k_plus"]["share_zero_exclusion"] == pytest.approx(0.122, abs=0.003)
    assert ieee["10k_to_100k"]["share_zero_exclusion"] > z["generous_ceiling"]
    for band in ("10k_to_100k", "100k_plus"):
        assert z["other_to_ieee_ratio_by_size"][band] > 1.5


# --- A14: the model against two utilities' daily outage maps ---------------

def _a14() -> dict:
    return _results("track8_falsification")["A14_real_daily_outages"]


def test_a14_rejects_lognormality_for_both_utilities():
    """The finding A14 exists for. Every series, PG&E without its shutoffs
    included, rejects normality of the logs and prefers both heavier-tailed
    families by a wide margin. The logs are right-skewed, which no symmetric
    tail model in A10 to A13 captures."""
    for key, s in _a14()["tail_shape"].items():
        assert s["shapiro_wilk_p"] < 1e-20, key
        assert s["tail_family"]["best"] != "normal", key
        aic = s["tail_family"]["aic"]
        assert aic["normal"] - aic["laplace"] > 160, key
        assert aic["normal"] - aic["student_t"] > 160, key
        assert s["log_skewness"] > 1.0, key


def test_a14_major_event_rates_exceed_even_the_laplace_model():
    """FINDINGS says the standard's rule flags more days a year on these series
    than a Laplace tail implies; that is a comparison with A12's 5.32."""
    a = _a14()
    assert a["laplace_med_days_per_year"] == pytest.approx(5.32, abs=0.01)
    for key, s in a["tail_shape"].items():
        assert s["med_days_per_year_at_2_5"] > a["laplace_med_days_per_year"], key


def test_a14_map_runs_above_the_filing_and_more_on_ordinary_days():
    f = _a14()["against_filing"]
    assert f["year"] == 2022 and f["observed_days"] >= 350
    assert 1.0 < f["map_over_filed_with"] < f["map_over_filed_without"]
    # the filing includes the former Gulf Power, the map does not
    assert f["filed_customers"] > f["map_customers_served"]


def test_a14_lognormal_overstates_most_scored_utility_years():
    a = _a14()
    s = a["summary"]
    assert s["n_utility_years"] == 3 and s["n_model_evaluable"] == 3
    assert s["n_lognormal_overstates"] == 2
    assert s["closest_model_counts"]["laplace"] == 2
    # the one year the log-normal model gets about right, it is within 7%
    near = [r for r in a["utility_years"] if r["lognormal_over_measured"] < 1.0]
    assert len(near) == 1 and abs(1.0 - near[0]["lognormal_over_measured"]) < 0.07
    lo, hi = s["measured_window_x_range"]
    assert 1.0 < lo and hi < 2.0
    # without shutoffs, PG&E's year joins the overstated ones
    assert a["summary_excl_psps"]["n_lognormal_overstates"] == 1


def test_a14_conclusions_survive_every_rule_it_varies():
    """FALSIFICATION states the robustness in words; these are the numbers."""
    a = _a14()
    for name, r in a["robustness"].items():
        assert r["normal_rejected_for_both"], name
        assert r["n_lognormal_overstates"] > r["n_model_evaluable"] / 2, name
        assert (r["closest_model_counts"]["laplace"]
                > r["closest_model_counts"]["lognormal"]), name
    loose = a["robustness"]["years_from_90_days"]
    assert loose["n_utility_years"] == 6 and loose["n_model_evaluable"] == 5
    assert loose["n_lognormal_overstates"] == 4
    assert loose["closest_model_counts"]["laplace"] == 4


def test_a14_provenance_separates_measured_from_modelled():
    from blinkrate.shared import provenance as pv
    f, b = "track8_falsification", "A14_real_daily_outages"
    assert pv.kind_of(f, b) == "outage_map_data"
    assert pv.kind_of(f, b, "measured_window_x") == "outage_map_data"
    for field in ("lognormal_predicted_x", "laplace_predicted_x",
                  "t_nu15_predicted_x", "lognormal_over_measured", "closest_model"):
        assert pv.kind_of(f, b, field) == "model_implied", field
    assert pv.kind_of(f, b, "filed_saidi_with") == "filed_data"


# --- the daily tail tool, validated before any real data arrives -----------

def _synthetic(kind: str, seed: int = 42):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2015-01-01", periods=365 * 8, freq="D")
    if kind == "lognormal":
        logs = rng.normal(5, 1.8, len(days))
    elif kind == "laplace":
        logs = rng.laplace(5, 1.8 / np.sqrt(2), len(days))
    else:
        logs = 5 + 1.8 * rng.standard_t(5, len(days)) / np.sqrt(5 / 3)
    return pd.Series(np.exp(logs), index=days)


@pytest.mark.parametrize("kind,expected", [("lognormal", "normal"),
                                           ("laplace", "laplace"),
                                           ("t5", "student_t")])
def test_daily_tail_tool_identifies_the_generating_family(kind, expected):
    sys.path.insert(0, str(ROOT / "tools"))
    import daily_tail_test as dt
    out = dt.analyse(_synthetic(kind))
    assert out["tail_family"]["best"] == expected


def test_daily_tail_tool_recovers_the_major_event_rate():
    """Log-normal data should flag near the nominal 2.27 days a year and
    Laplace near 5.32. If the tool is off here it is off on real data."""
    sys.path.insert(0, str(ROOT / "tools"))
    import daily_tail_test as dt
    assert dt.analyse(_synthetic("lognormal"))["med_days_per_year_at_2_5"] == \
        pytest.approx(2.27, abs=1.0)
    assert dt.analyse(_synthetic("laplace"))["med_days_per_year_at_2_5"] == \
        pytest.approx(5.32, abs=1.5)


def test_hill_index_is_documented_as_non_diagnostic():
    """A wide log-normal produces a Hill index inside Ahmad & Dobson's measured
    range. That is why the tool and FINDINGS both refuse to treat an in-range
    Hill index as evidence of a Pareto tail. Pinned so the caveat cannot be
    quietly dropped while the phenomenon it describes is still true."""
    sys.path.insert(0, str(ROOT / "tools"))
    import daily_tail_test as dt
    out = dt.analyse(_synthetic("lognormal"))
    assert out["tail_family"]["best"] == "normal"
    assert out["hill_alpha_within_ahmad_dobson"] is True
    assert "not diagnostic" in (ROOT / "tools" / "daily_tail_test.py").read_text()


def test_archived_abstract_reflects_the_withdrawal():
    """CITATION.cff and .zenodo.json are what a citing reader sees, and they are
    archived permanently on release. They must carry the evidence-window
    magnitude and the withdrawal, and must not quote the withdrawn comparison as
    a finding."""
    import re
    fr = _results("track8_falsification")["A13_evidence_grounded_window"][
        "fleet_range_on_widest_evidence_window"]
    cff = re.sub(r"\s+", " ", (ROOT / "CITATION.cff").read_text())
    assert f"{fr['laplace']['range_x']:.2f}x to {fr['lognormal']['range_x']:.2f}x" in cff
    assert "withdrawn" in cff
    for withdrawn in ("6.18x", "1.58 times", "more than the whole industry"):
        assert withdrawn not in cff, f"abstract quotes the withdrawn claim: {withdrawn}"
    zen = json.loads((ROOT / ".zenodo.json").read_text())["description"]
    assert "withdrawn" in zen


# --------------------------------------------------------------------------
# reproducibility: the bunching fit must not depend on the LAPACK build
# --------------------------------------------------------------------------

_BUNCHING_GRID = [(d, w, lo) for d in (3, 4, 5, 7) for w in (0.02, 0.05, 0.10)
                  for lo in (0.2, 0.3, 0.5)]


def _exact_excess_mass(r, window, degree, fit_lo):
    """The bunching point estimate in exact rational arithmetic: least squares
    by Gauss-Jordan elimination over Fractions, so no floating point anywhere.
    The reference both polynomial bases are judged against."""
    from fractions import Fraction
    edges = np.arange(fit_lo, 1.0 + 1e-9, 0.01)
    centers = (edges[:-1] + edges[1:]) / 2
    in_window = centers > (1 - window)
    b = np.digitize(r, edges) - 1
    counts = np.bincount(b[(b >= 0) & (b < centers.size)], minlength=centers.size)
    xs = [Fraction(float(x)) for x in centers]
    fit = [i for i in range(len(xs)) if not in_window[i]]
    win = [i for i in range(len(xs)) if in_window[i]]
    k = degree + 1
    m = [[sum(xs[i] ** (a + c) for i in fit) for c in range(k)]
         + [sum(xs[i] ** a * int(counts[i]) for i in fit)] for a in range(k)]
    for c in range(k):
        p = next(i for i in range(c, k) if m[i][c] != 0)
        m[c], m[p] = m[p], m[c]
        m[c] = [v / m[c][c] for v in m[c]]
        for i in range(k):
            if i != c and m[i][c] != 0:
                m[i] = [x - m[i][c] * y for x, y in zip(m[i], m[c])]
    coef = [m[i][k] for i in range(k)]
    cf = sum(max(Fraction(0), sum(coef[a] * xs[i] ** a for a in range(k)))
             for i in win)
    return float(Fraction(int(counts[in_window].sum())) / cf)


def test_bunching_fit_is_well_conditioned():
    """The counterfactual polynomial is fitted in a Legendre basis on the
    fitted points' rescaled range, condition number 3.7 at worst on this grid.
    The raw power basis it replaced reaches 2.3e8, which left the last digits
    of every bunching result to the LAPACK build and failed CI's byte-identity
    check under numpy 2.5. Scaling to the full bin range instead reaches 352.
    If either regression comes back, this fails before CI does."""
    from blinkrate.track3_med_sensitivity import bunching_design_for
    worst = max(np.linalg.cond(bunching_design_for(lo, w, d)[0])
                for d, w, lo in _BUNCHING_GRID)
    assert worst < 10, f"bunching design condition number {worst:.3g}"


@pytest.mark.parametrize("degree,window,fit_lo", [(5, 0.05, 0.30),   # headline
                                                  (7, 0.05, 0.50),   # worst-conditioned
                                                  (7, 0.02, 0.50)])
def test_bunching_estimate_matches_exact_arithmetic(degree, window, fit_lo):
    """Same estimator, now within about 1e-14 of exact rational arithmetic. The
    old power basis missed by up to 1.6e-9 relative, as large as the rounding
    step of the ninth significant figure that results are stored to."""
    from blinkrate.track3_med_sensitivity import excess_mass_at_zero_exclusion
    df = ingest.analysis_sample()
    got = excess_mass_at_zero_exclusion(df, window=window, degree=degree,
                                        n_boot=10, fit_lo=fit_lo)["excess_mass_ratio"]
    want = _exact_excess_mass(df["retained_share"].to_numpy(), window, degree, fit_lo)
    assert got == pytest.approx(want, rel=1e-12)
