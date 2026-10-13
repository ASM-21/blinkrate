#!/usr/bin/env python3
"""Run one utility's filed numbers through the exclusion engine.

    python tools/utility_profile.py --name "Commonwealth Edison"
    python tools/utility_profile.py --id 5416 --state NC --figure
    python tools/utility_profile.py --name "Georgia Power" --peers
    python tools/utility_profile.py --pair 200 120               # any filed pair
    python tools/utility_profile.py --pair 200 120 --tails       # and its tail sensitivity

Takes the (SAIDI with MED, SAIDI without MED) pair a utility actually filed and
reports what it would have filed at other threshold values, where it sits
against its peers, and how much of its own year-to-year movement lives in the
excluded portion rather than in everyday outage minutes.

Same caveat as track 3, and it is not a footnote: the counterfactual columns are
model-implied under IEEE 1366's own log-normal assumption for daily SAIDI. The
filed columns are what the utility reported. Do not present the two as the same
kind of number.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blinkrate.shared import finite_sample as fs  # noqa: E402
from blinkrate.shared import ingest  # noqa: E402
from blinkrate.shared import reliability_metrics as rm  # noqa: E402
from blinkrate.shared.io import PALETTE, save_figure, style_axes  # noqa: E402

BETAS = np.array([1.5, 2.0, 2.5, 3.0])


def select(df: pd.DataFrame, name: str | None, uid: int | None,
           state: str | None) -> pd.DataFrame:
    sub = df
    if uid is not None:
        sub = sub[sub["utility_id"] == uid]
    if name:
        sub = sub[sub["utility_name"].str.contains(name, case=False, na=False)]
    if state:
        sub = sub[sub["state"].str.upper() == state.upper()]
    return sub.sort_values(["utility_id", "state", "year"])


def profile(sub: pd.DataFrame, full: pd.DataFrame) -> pd.DataFrame:
    r = sub["retained_share"].to_numpy()
    sigma = fs.implied_sigma_fs(r)
    curve = fs.sensitivity_curve_fs(r, BETAS)
    saidi_with = sub["saidi_with"].to_numpy()

    rows = []
    for i, (_, row) in enumerate(sub.iterrows()):
        peers = full[(full["year"] == row["year"])
                     & (full["ownership_class"] == row["ownership_class"])]
        rec = {
            "year": int(row["year"]),
            "state": row["state"],
            "customers": int(row["customers"]),
            "filed_with_MED": row["saidi_with"],
            "filed_without_MED": row["saidi_without"],
            "excluded_min": row["excluded_minutes"],
            "excluded_pct": 100 * (1 - row["retained_share"]),
            "implied_sigma": sigma[i],
            # where this utility sits among same-ownership peers that year
            "pctile_excluded_vs_peers": 100 * float(
                (peers["excluded_share"] < row["excluded_share"]).mean()),
            "pctile_saidi_without_vs_peers": 100 * float(
                (peers["saidi_without"] < row["saidi_without"]).mean()),
        }
        for k, b in enumerate(BETAS):
            rec[f"at_beta_{b}"] = (saidi_with[i] * curve[i, k]
                                   if np.isfinite(curve[i, k]) else np.nan)
        rows.append(rec)
    return pd.DataFrame(rows)


def movement(prof: pd.DataFrame) -> dict:
    """Split this utility's own change between excluded and everyday minutes."""
    if len(prof) < 2:
        return {}
    a, b = prof.iloc[0], prof.iloc[-1]
    d_with = b["filed_with_MED"] - a["filed_with_MED"]
    d_without = b["filed_without_MED"] - a["filed_without_MED"]
    d_excl = b["excluded_min"] - a["excluded_min"]
    return {
        "span": f"{int(a['year'])} to {int(b['year'])}",
        "change_with_MED": d_with,
        "change_without_MED": d_without,
        "change_excluded": d_excl,
        "share_of_change_in_excluded": (d_excl / d_with) if d_with else np.nan,
        "range_with_MED": prof["filed_with_MED"].max() - prof["filed_with_MED"].min(),
        "range_without_MED": (prof["filed_without_MED"].max()
                              - prof["filed_without_MED"].min()),
    }


def make_figure(prof: pd.DataFrame, label: str) -> Path:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    yrs = prof["year"]
    ax.plot(yrs, prof["filed_with_MED"], marker="o", lw=2.2,
            color=PALETTE["with_med"], label="filed, with major event days")
    ax.plot(yrs, prof["filed_without_MED"], marker="o", lw=2.2,
            color=PALETTE["without_med"], label="filed, without major event days")
    ax.fill_between(yrs, prof["filed_without_MED"], prof["filed_with_MED"],
                    color=PALETTE["accent"], alpha=0.18, label="excluded")
    ax.plot(yrs, prof["at_beta_1.5"], marker="s", ms=4, ls="--", lw=1.6,
            color=PALETTE["muted"], label="counterfactual at $\\beta$ = 1.5")
    # The panel jumps 2015 -> 2022. Drawing a straight segment across the hole
    # implies a trajectory through years this repo does not have, so the gap is
    # shaded and labelled instead of left to look continuous.
    gaps = [(a, b) for a, b in zip(list(yrs)[:-1], list(yrs)[1:]) if b - a > 1]
    for a, b in gaps:
        ax.axvspan(a, b, color="white", alpha=0.0)
        ax.axvspan(a + 0.08, b - 0.08, color=PALETTE["grid"], alpha=0.55, zorder=0)
        ax.text((a + b) / 2, ax.get_ylim()[1] * 0.03, "no filings vendored",
                ha="center", va="bottom", fontsize=7.5, color=PALETTE["muted"],
                rotation=0, zorder=1)
    ax.set_xticks(list(yrs))
    ax.set_xlabel("EIA-861 filing year")
    ax.set_ylabel("SAIDI (min/yr)")
    ax.set_title(f"{label}: filed reliability and the exclusion underneath it",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8.5)
    fig.text(0.005, -0.05,
             "Filed series are reported values. The dashed counterfactual is "
             "model-implied under IEEE 1366's own log-normal\nassumption for "
             "daily SAIDI (see FALSIFICATION.md, attack A1).",
             fontsize=7.5, color=PALETTE["muted"], ha="left", va="top")
    style_axes(ax)
    slug = "".join(c if c.isalnum() else "_" for c in label.lower())[:40]
    return save_figure(fig, f"profile_{slug}")


def profile_pair(saidi_with: float, saidi_without: float, tails: bool) -> int:
    """Counterfactual sweep for any (SAIDI with MED, SAIDI without MED) pair.

    For utilities not in the EIA-861 panel, or for someone checking their own
    filing. With --tails it repeats the sweep under heavier-tailed daily
    outages, re-inverting dispersion each time so every row reproduces the same
    filed pair, which is attack A10 applied to one utility.
    """
    if not (saidi_with > 0 and 0 <= saidi_without <= saidi_with):
        print("need SAIDI_WITH > 0 and 0 <= SAIDI_WITHOUT <= SAIDI_WITH")
        return 1
    r = saidi_without / saidi_with
    print(f"\nfiled: {saidi_with:.1f} with major event days, {saidi_without:.1f} "
          f"without  |  retained share {r:.3f}, excluded {100 * (1 - r):.1f}%\n")

    sigma = fs.implied_sigma_fs(np.array([r]))[0]
    if not np.isfinite(sigma):
        print("This pair is outside what IEEE 1366's own log-normal model can "
              "produce\n(it excludes less than any non-negative dispersion "
              "would, or more than the\ncalibration grid reaches). No "
              "counterfactual is computed; that is a finding, not a failure.")
        return 0

    rows = [("log-normal (IEEE 1366's assumption)", None)]
    if tails:
        rows += [("Student-t, nu = 30", 30.0), ("Student-t, nu = 15", 15.0),
                 ("Student-t, nu = 5", 5.0)]
    betas = np.array([1.5, 2.0, 2.5, 3.0])
    print(f"{'daily outage distribution':38s}" +
          "".join(f"{'beta ' + str(b):>11s}" for b in betas) + f"{'sweep':>9s}")

    from blinkrate.track8_falsification import _tail_surface
    rng = np.random.default_rng(20260926)
    grid = np.round(np.arange(0.1, 6.01, 0.1), 3)
    for label, nu in rows:
        if nu is None:
            curve = fs.retained_share_fs(sigma, betas).ravel()
        else:
            surf = _tail_surface(nu, grid, betas, 250, rng)
            r25 = surf[:, 2]
            order = np.argsort(r25)
            if not (r25.min() <= r <= r25.max()):
                print(f"{label:38s}  outside this model's range")
                continue
            sig = np.interp(r, r25[order], grid[order])
            curve = np.array([np.interp(sig, grid, surf[:, j])
                              for j in range(betas.size)])
        vals = saidi_with * curve
        print(f"{label:38s}" + "".join(f"{v:11.1f}" for v in vals) +
              f"{vals[-1] / vals[0]:8.2f}x")

    print("\nEvery row reproduces the filed pair at beta 2.5 by construction. "
          "How far the\nother columns spread is the part that depends on the "
          "tail assumption; see\nFALSIFICATION.md, attack A10." if tails else
          "\nModel-implied under IEEE 1366's own log-normal assumption. Add "
          "--tails to see\nhow much the sweep depends on it (FALSIFICATION.md, "
          "attack A10).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", help="substring of the utility name")
    ap.add_argument("--id", type=int, help="EIA utility id")
    ap.add_argument("--state", help="two-letter state code")
    ap.add_argument("--figure", action="store_true", help="write a figure")
    ap.add_argument("--peers", action="store_true",
                    help="list the nearest same-size peers in the latest year")
    ap.add_argument("--pair", nargs=2, type=float,
                    metavar=("SAIDI_WITH", "SAIDI_WITHOUT"),
                    help="profile any filed pair instead of an EIA-861 utility")
    ap.add_argument("--tails", action="store_true",
                    help="with --pair, repeat the sweep under heavier tails")
    args = ap.parse_args()
    if args.pair:
        return profile_pair(args.pair[0], args.pair[1], args.tails)
    if not args.name and args.id is None:
        ap.error("give --name, --id or --pair")

    full = ingest.analysis_sample()
    sub = select(full, args.name, args.id, args.state)
    if sub.empty:
        print("no matching utility-state-years in the panel")
        return 1
    if sub[["utility_id", "state"]].drop_duplicates().shape[0] > 1:
        print("matches more than one utility-state; narrow with --id / --state:\n")
        print(sub[["utility_id", "utility_name", "state"]].drop_duplicates()
              .to_string(index=False))
        return 1

    label = f"{sub.iloc[0]['utility_name']} ({sub.iloc[0]['state']})"
    prof = profile(sub, full)

    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(f"\n{label}  |  EIA id {int(sub.iloc[0]['utility_id'])}  |  "
          f"{sub.iloc[0]['ownership_class']}  |  reports under "
          f"{sub.iloc[0]['standard']}\n")

    filed = prof[["year", "filed_with_MED", "filed_without_MED", "excluded_min",
                  "excluded_pct", "implied_sigma"]].round(2)
    print("FILED\n" + filed.to_string(index=False))

    cf = prof[["year"] + [f"at_beta_{b}" for b in BETAS]].round(1)
    cf.columns = ["year"] + [f"beta {b}" for b in BETAS]
    print("\nWHAT WOULD HAVE BEEN FILED AT OTHER THRESHOLDS (model-implied)")
    print(cf.to_string(index=False))

    rank = prof[["year", "pctile_excluded_vs_peers",
                 "pctile_saidi_without_vs_peers"]].round(1)
    print("\nPERCENTILE AMONG SAME-OWNERSHIP PEERS THAT YEAR")
    print(rank.to_string(index=False))

    mv = movement(prof)
    if mv:
        print(f"\nOWN MOVEMENT, {mv['span']}")
        print(f"  with MED     {mv['change_with_MED']:+8.1f} min   "
              f"(range across years {mv['range_with_MED']:.1f})")
        print(f"  without MED  {mv['change_without_MED']:+8.1f} min   "
              f"(range across years {mv['range_without_MED']:.1f})")
        print(f"  excluded     {mv['change_excluded']:+8.1f} min")
        if np.isfinite(mv["share_of_change_in_excluded"]):
            print(f"  share of the with-MED change that sits in the excluded "
                  f"part: {100 * mv['share_of_change_in_excluded']:.1f}%")

    if args.peers:
        yr = int(prof["year"].max())
        row = sub[sub["year"] == yr].iloc[0]
        pool = full[(full["year"] == yr)
                    & (full["ownership_class"] == row["ownership_class"])].copy()
        pool["size_gap"] = (np.log(pool["customers"]) - np.log(row["customers"])).abs()
        near = pool.nsmallest(9, "size_gap")
        print(f"\nNEAREST-SIZE {row['ownership_class']} PEERS IN {yr}")
        print(near[["utility_name", "state", "customers", "saidi_with",
                    "saidi_without", "excluded_share"]]
              .round(3).to_string(index=False))

    if args.figure:
        print(f"\nfigure: {make_figure(prof, label)}")

    print("\nCounterfactual columns are model-implied under IEEE 1366's own "
          "log-normal assumption.\nFiled columns are reported values. See "
          "FALSIFICATION.md attack A1 for what that assumption is worth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
