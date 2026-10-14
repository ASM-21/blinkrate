#!/usr/bin/env python3
"""How far do the quoted figures move when only the calibration seed changes?

    python tools/seed_spread.py              # five other seeds, about ten minutes
    python tools/seed_spread.py --seeds 2

The calibration surface (blinkrate/shared/finite_sample.py) is a seeded Monte
Carlo simulation. Fixing the seed makes every model-implied figure reproduce bit
for bit, which is what CI checks, but it does not make the figure exact: another
seed is another realization of the same surface. This tool rebuilds the surface
from the next few seeds, regenerates every result into a temporary directory,
and lists every figure the claims guard checks that moves, against the guard's
own tolerance. Figures computed straight from the filings do not touch the
surface and never move.

Nothing in the repository is written. Each seed runs in a fresh process.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Runs in a fresh interpreter per seed, so no track can carry state across seeds.
_WORKER = """
import contextlib, os, sys
from pathlib import Path
seed, out = int(sys.argv[1]), Path(sys.argv[2])
from blinkrate.shared import finite_sample as fs, io
fs._CACHED = fs.build_calibration(seed=seed)
io.RESULTS, io.FIGURES = out / "results", out / "figures"
sys.argv = ["run_all"]
from blinkrate import run_all
with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
    run_all.main()
"""


def claim_values(results_dir: Path) -> list[tuple[str, float, float]]:
    """The guard's (quoted text, value, tolerance) list, computed from results_dir."""
    spec = importlib.util.spec_from_file_location(
        "check_claims", ROOT / "tools" / "check_claims.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.RESULTS = Path(results_dir)
    return guard.claims()


_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _rest(text: str) -> str:
    """The claim with its first number masked: what the guard matches exactly."""
    return _NUMBER.sub("#", text, count=1)


def compare(base: list, runs: list[list]) -> list[dict]:
    """Every claim that changes in any run, with its range and tolerance.

    The guard checks a claim's first number against a tolerance and every other
    number in it exactly. So a claim moves if its first number moves, and it
    breaks the guard either way when any other number in it changes, which is
    how table rows that lead with a year or a count move.
    """
    rows = []
    for run in runs:
        if len(run) != len(base):
            raise SystemExit("claim lists differ in length; cannot align them")
    for i, (text, v0, tol) in enumerate(base):
        vals = [run[i][1] for run in runs]
        rest_changed = any(_rest(run[i][0]) != _rest(text) for run in runs)
        if all(v == v0 for v in vals) and not rest_changed:
            continue
        dev = max(abs(v - v0) for v in vals)
        rows.append({"claim": text, "committed": v0, "min": min(vals),
                     "max": max(vals), "max_rel": dev / abs(v0) if v0 else float("inf"),
                     "tolerance": tol, "other_numbers_change": rest_changed,
                     "exceeds_tolerance": dev > tol or rest_changed})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5,
                    help="how many seeds after the committed one (default 5)")
    args = ap.parse_args()
    from blinkrate.shared.finite_sample import SEED

    base = claim_values(ROOT / "results")
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(1, args.seeds + 1):
            out = Path(tmp) / f"seed_{SEED + k}"
            print(f"seed {SEED + k}: rebuilding the surface and every result",
                  flush=True)
            subprocess.run([sys.executable, "-W", "ignore", "-c", _WORKER,
                            str(SEED + k), str(out)], cwd=ROOT, check=True)
            runs.append(claim_values(out / "results"))

    rows = compare(base, runs)
    print(f"\n{len(rows)} of {len(base)} guarded figures move across {len(runs)} "
          f"other seeds (committed seed {SEED})\n")
    print(f"{'figure as quoted':40s} {'committed':>10s} {'min':>10s} {'max':>10s} "
          f"{'max move':>9s} {'guard tol':>9s}")
    for r in rows:
        flag = "  beyond tolerance" if r["exceeds_tolerance"] else ""
        if r["other_numbers_change"]:
            flag += " (other numbers in it change)"
        print(f"{r['claim'][:40]:40s} {r['committed']:10.4g} {r['min']:10.4g} "
              f"{r['max']:10.4g} {r['max_rel']:9.2%} {r['tolerance']:9.3g}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
