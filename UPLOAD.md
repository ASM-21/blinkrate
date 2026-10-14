# Publishing blinkrate

Everything here is already done except the push, which needs your GitHub
credentials. Commits are authored as `Andrew Morrissey
<77601626+ASM-21@users.noreply.github.com>`, the address GitHub attributes to
ASM-21. Tags `v1.0.0` to `v1.3.0` are annotated and point at verified commits.

## 1. Verify from nothing, one last time

```bash
unzip blinkrate-v1.3.0.zip && cd blinkrate
./verify.sh            # isolated venv, cold install, every check CI makes
./verify.sh --fast     # reuses installed numpy/pandas/scipy if memory is tight
```

`verify.sh` is CI run on your machine, and needs Python 3.10 or later. It builds
a throwaway environment, rebuilds the calibration surface from its seed and
checks it bit for bit, regenerates every result from the vendored EIA-861 files,
checks those byte for byte against the committed ones, then runs the test suite
and the claims guard. It prints `ALL GREEN` or stops at the first failure.

It regenerates the figures in place as well. Their pixels depend on the
matplotlib version, so `git status` may list modified PNGs afterwards, and
`git checkout -- figures/` restores the committed ones. Nothing else is touched.

To rerun only the byte check:

```bash
python -m blinkrate.run_all
git diff --exit-code -- results/     # no output means byte-identical
```

## 2. Create the repository and push

On github.com, create **ASM-21/blinkrate**: public, and *without* a README,
licence or .gitignore, since all three already exist and GitHub's copies would
collide with the history.

```bash
cd blinkrate
git remote add origin git@github.com:ASM-21/blinkrate.git
git push -u origin main
git push origin --tags
```

Pushing all four tags in one push should not start CI runs for them: GitHub
creates no push event when more than three tags arrive at once. If you push tags
separately, `v1.0.0` and `v1.1.0` will run with the workflow they shipped with
and fail, because they store results to 12 significant figures and predate the
bunching fix (CHANGELOG v1.2.0, Fixed). That is a record of the problem, not a
regression, and the README badge follows `main` either way.

Suggested repository description:

> How much of a US utility's reported reliability number is the measurement rule
> rather than the grid? EIA-861, 2013-2018 and 2022, fourteen adversarial attacks.

Topics: `saidi`, `ieee-1366`, `electric-reliability`, `eia-861`,
`distribution-grid`, `falsification`, `reproducible-research`.

## 3. After the push

- **CI.** Open the Actions tab and confirm the run on `main` is green. It
  rebuilds the calibration cache bit for bit, regenerates every result, fails on
  any byte difference, then runs the tests and the claims guard.
- **Release.** Create a GitHub release from tag `v1.3.0` and paste the v1.3.0
  section of CHANGELOG.md as the notes.
- **DOI (optional).** Enabling the repository in Zenodo *before* creating the
  release mints a DOI from `.zenodo.json`. Add the DOI badge to the README and
  the `doi:` field to CITATION.cff afterwards, in one commit.

## What was checked before this was written

- No absolute paths, placeholder owners, example.com addresses, or TODO markers
  in tracked files.
- Single commit author across the whole history, the attributable address above.
- Only public data: EIA Form 861, a US federal government work; two utilities'
  outage-map snapshots from public git-scraping archives (counts only, sources in
  NOTICE); and published literature parameters. No utility-internal, customer or
  employer data anywhere in the tree or the history. The README's independence disclaimer is enforced by
  the claims guard.
- Bundled data licences recorded in NOTICE: EIA-861 is public domain; the three
  GitHub mirrors it was retrieved through are MIT, BSD-2-Clause, and unlicensed
  redistribution of the public-domain originals. The outage-map archives are
  Apache-2.0 (PG&E) and unlicensed (FPL), and only counts are redistributed.
  `python tools/build_outage_snapshots.py` rebuilds those files byte for byte.
- Versions agree across pyproject.toml, CITATION.cff, .zenodo.json and the newest
  CHANGELOG heading, and a test fails if they drift.
- Every CI step passes from a fresh clone on the oldest and newest supported
  library versions, under both Intel AVX-512 and AMD Zen 3 code paths, since a
  hosted runner may have either CPU. Ranges are in requirements-lock.txt.

## If something fails after pushing

Do not force-push over a published tag. Fix forward in a new commit, re-run
`./verify.sh`, and cut `v1.3.1`. CHANGELOG.md is where a reader looks to find out
what moved, so every correction goes there first.
