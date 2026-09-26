# Contributing

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

**2. Run the engine on real daily SAIDI.** Q1's sweep is model-implied because
no daily series is public at national scale. Some state commissions require
daily outage logs in annual reliability filings. One utility's five-year daily
series replaces the inversion with a measurement and settles attack A1 outright.
*Finish line:* `simulate_med_exclusion()` run on real daily data, with the
realized retained share compared against what the inversion predicts from that
utility's published annual pair. *Start at:*
`blinkrate/shared/reliability_metrics.py`.

**3. Supply the 2019-2021 filings.** The panel jumps 2018 to 2022, so no
movement after 2018 can be dated. If a GitHub mirror of those years exists,
adding it is a three-line change to `_HEADER_ROWS` and `YEARS_AVAILABLE`.
*Finish line:* seven becomes ten filing years and every test still passes.
*Start at:* `blinkrate/shared/ingest.py` and `docs/DATA_ACCESS.md`.

**4. Supply FERC Form 1.** The only genuinely blocked track. With a capex
series, Q5 gets a spending variable and the vegetation-management question stops
being marked BLOCKED. *Finish line:* `track4_cause_exclusions.py` loses its
BLOCKED status. *Start at:* `docs/DATA_ACCESS.md` for the search record.

**5. Break attack A8's part one.** It compares a model-implied sweep against
observed spread, so it inherits A1's log-normality dependence: under
heavier-tailed daily outages the sweep narrows and the ratio of 1.58 falls. Work
out how heavy the tail has to be before the criterion fails, and whether real
daily data is anywhere near that. *Finish line:* the breaking point stated as a
number. *Start at:* `a1b_heavy_tail_matched` and
`a8_stated_falsification_criterion` in `blinkrate/track8_falsification.py`.

**6. An exogenous aggregation weight.** Track 9 reweights the national figure
six ways, all derived from the filings themselves. A weight from outside the
data, such as state population, would let the national figure be checked rather
than only reweighted. *Start at:* `blinkrate/track9_aggregation.py`.

## The bar for a new number

Anything quoted in README.md, FINDINGS.md or FALSIFICATION.md must be:

1. produced by code in `blinkrate/`, written to `results/` as JSON;
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
./verify.sh                       # clean venv, full suite, guard
```

Install editable (`-e`). The vendored EIA files and the calibration cache are
resolved relative to the repository root rather than to the installed package,
so this is a clone-and-run research repo, not a library you can `pip install`
from a wheel and use elsewhere. `verify.sh` installs editable for that reason.

`data/calibration_med.npz` is generated. Rebuild it with
`python -m blinkrate.shared.finite_sample` (about 20 seconds, and bit-identical
to the committed cache since it is fully seeded). Rebuilding it
changes track 3, 6 and 8 numbers at the third decimal, so rerun the tracks and
the guard afterwards.

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
