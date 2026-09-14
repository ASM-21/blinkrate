"""Run every track in dependency order and write results/ and figures/.

    python -m blinkrate.run_all
    python -m blinkrate.run_all --skip 8      # track 8 takes several minutes

Order matters. The shared calibration is built first because tracks 3, 6 and 8
invert it. Track 7 validates the engine, and is run before anything is believed
rather than after. Track 9 runs after track 3 because it reuses track 3's
counterfactual. Track 8 runs last because it re-executes pieces of 1, 2, 3 and 6
under alternative specifications.
"""

from __future__ import annotations

import argparse
import time

from . import (track1_investment, track2_weather_split, track3_med_sensitivity,
               track4_cause_exclusions, track5_undergrounding, track6_ownership,
               track7_validation, track8_falsification, track9_aggregation)
from .shared import finite_sample

TRACKS = {
    7: ("validation (engine + source data)", track7_validation),
    1: ("capital deployment vs reliability", track1_investment),
    2: ("weather vs performance split", track2_weather_split),
    3: ("MED methodology sensitivity [headline]", track3_med_sensitivity),
    6: ("ownership stratification", track6_ownership),
    5: ("undergrounding breakeven", track5_undergrounding),
    4: ("cause-specific exclusions [track 4 blocked]", track4_cause_exclusions),
    9: ("aggregation rule sensitivity", track9_aggregation),
    8: ("adversarial falsification", track8_falsification),
}
ORDER = [7, 1, 2, 3, 6, 9, 5, 4, 8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", type=int, nargs="*", default=[],
                    help="track numbers to skip")
    args = ap.parse_args()

    finite_sample.calibration()  # build or load the surface once, up front
    print("calibration surface ready")

    for n in ORDER:
        if n in args.skip:
            print(f"track {n}: skipped")
            continue
        label, module = TRACKS[n]
        t0 = time.time()
        module.run()
        print(f"track {n}: {label} ... {time.time() - t0:.1f}s")
    print("done. results/ and figures/ written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
