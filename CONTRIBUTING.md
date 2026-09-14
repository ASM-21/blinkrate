# Contributing

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
