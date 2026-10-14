# Contributing

## Using it on your own numbers

`python tools/utility_profile.py --pair SAIDI_WITH SAIDI_WITHOUT --tails` runs
any filed pair through the engine, including utilities outside the EIA-861
panel, and shows how much the counterfactual depends on the tail assumption.
If you have real daily SAIDI for a utility, contribution 2 below is the most
valuable thing anyone could add.

## Good first contributions

Ordered by how much each would change a conclusion. Each names a finish line and
a starting file.

**1. Attack the uncorroborated numbers.** Four results were not found in the
literature search (LITERATURE.md), which makes them the most likely to be wrong:
the closed-form inversion `r = Phi(beta - sigma)`, the 40-57% rank reversal, the
2.07x aggregation spread, and the hurricane-track placebo. *Finish line:* an
issue showing any of them fails under a specification the repository does not
already test. *Start at:* `blinkrate/shared/reliability_metrics.py` and
`blinkrate/track8_falsification.py`.

**2. Run the tail test on more daily outage data.** Every model-implied number
here rests on daily SAIDI being log-normal. Attack A14 found it false for the two
utilities with daily data in this repository, PG&E and FPL, measured from
archived outage maps; whether that holds beyond two storm-prone utilities is
open, and the one formal fit test in the literature (Fumagalli et al. 2006,
Italian districts) found thinner tails. `tools/daily_tail_test.py` runs the same
test on any series. ORNL's EAGLE-I county data (Scientific Data 2024, DOI
10.1038/s41597-024-03095-5, via Globus or Figshare) works directly with
`--eaglei --state XX`. Another utility's outage-map archive, if one exists in
git, can be added to `tools/build_outage_snapshots.py` and then joins A14
itself. *Finish line:* the tool's output for at least one more utility or state,
committed under `results/external/` with the source recorded, or a third archive
in A14. Read the tool's Hill caveat before quoting a tail index.

**3. Supply the 2019-2021 filings.** The panel jumps 2018 to 2022. Catalyst
Cooperative's PUDL has them as `core_eia861__yearly_reliability`, distributed
through S3, Kaggle and Zenodo, none reachable from where this was built. Mind
PUDL issue 4907, a column swap in the 2024 rows. *Finish line:* the three years
loaded through `blinkrate/shared/ingest.py` with the same position-based column
map, checked against EIA's raw workbooks, and every test still passing.

**4. Supply FERC Form 1.** The only genuinely blocked track. With a capex
series, Q5 gets a spending variable and the vegetation-management question stops
being marked BLOCKED. *Finish line:* `track4_cause_exclusions.py` loses its
BLOCKED status. *Start at:* `docs/DATA_ACCESS.md` for the search record.

**5. Find a realistic window where the withdrawn comparison holds.** Attack
A13 found the threshold's effect on one utility smaller than the spread between
utilities on every window the literature supports. The strongest way to reverse
that is evidence that realistic major-event frequencies extend well past fifteen
a year, or below one, for large US utilities. *Finish line:* a citable source,
added to `EVIDENCE_WINDOWS` in `blinkrate/track8_falsification.py`, and A13
re-run. If the comparison then holds, the withdrawal in FINDINGS comes out.

**6. An exogenous aggregation weight.** Track 9 reweights the national figure
six ways, all derived from the filings themselves. A weight from outside the
data, such as state population, would let the national figure be checked rather
than only reweighted. *Start at:* `blinkrate/track9_aggregation.py`.

## The bar for a new number

Anything quoted in README.md, FINDINGS.md or FALSIFICATION.md must be:

1. produced by code in `blinkrate/`, written to `results/` as JSON, and
   declared `filed_data`, `model_implied` or `outage_map_data` in
   `blinkrate/shared/provenance.py` (an undeclared result refuses to save);
2. pinned by a test in `tests/` with a tolerance tight enough to fail on a real
   change;
3. registered in `tools/check_claims.py` so the build breaks if the prose and the
   code disagree.

A finding that lives only in a sentence stops being true silently. That is the
failure mode this repo is arranged against.

## Running things

```bash
pip install -e ".[dev]"
python -m blinkrate.run_all       # all tracks; track 8 takes a few minutes
python -m blinkrate.run_all --skip 8
pytest
python tools/check_claims.py
./verify.sh                       # every CI check, in a clean venv
```

Install editable (`-e`). The vendored EIA files and the calibration cache are
resolved relative to the repository root rather than to the installed package,
so this is a clone-and-run research repo, not a library you can `pip install`
from a wheel and use elsewhere. `verify.sh` installs editable for that reason.

`data/daily/` is derived from two public outage-map archives and rebuilt with
`python tools/build_outage_snapshots.py`, which clones them and needs network
access to GitHub; the output must match the checksums in `data/daily/README.md`,
and a test holds the vendored files to them.

`data/calibration_med.npz` is generated. Rebuild it with
`python -m blinkrate.shared.finite_sample` (about 20 seconds, and bit-identical
to the committed cache since it is fully seeded), or add `--check` to compare a
fresh build with the committed cache without writing, which is what CI runs.

The seed makes the surface's Monte Carlo noise reproducible; it does not remove
it. Rebuilt from five other seeds, 19 of the 118 guarded figures change, every
one of them model-implied or holding a model-implied prediction, by up to 7.7%,
and 13 change by more than the guard's tolerance (the 7.66x threshold range
lands between 7.69x and 7.75x).
`python tools/seed_spread.py` measures this. Changing the seed or the simulation
count therefore changes quoted figures: rerun the tracks and the guard after
either, and update the prose.

## Style rules that exist for a reason

**Say what changed.** If a track cannot answer its original question because the
data is unreachable, change the question and state the substitution at the top of
the module and in the results payload. Do not proxy quietly. Track 1 and track 4
are the worked examples.

**Figure titles are prose.** `tools/check_claims.py` scans the string literals
passed to `set_title`, `fig.text`, `ax.text` and `annotate` in every track for
the same overclaiming patterns it enforces in the markdown. This exists because
a track 9 figure once asserted something that track's own numbers contradicted
and nothing caught it.

**Hedge in the prose, not just the docstring.** `tools/check_claims.py` enforces
a list of required hedges and a list of forbidden phrasings. If you find yourself
wanting to delete one, that is the signal to weaken the claim instead.

**Attacks belong in track 8.** A robustness check buried in a track is a
robustness check nobody will find. Two attacks in the current set landed and
changed the writeups; that is the intended outcome, not an embarrassment.

**Report broken attacks too.** A4's first version kept a utility if any one of
its four years was in range, which dropped nobody and passed vacuously. It is
written up in FALSIFICATION rather than quietly fixed.
