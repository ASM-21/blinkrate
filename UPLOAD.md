# Publishing blinkrate

Everything here is already done except the push, which needs your GitHub
credentials. Commits are authored as `Andrew Morrissey
<77601626+ASM-21@users.noreply.github.com>`, the address GitHub attributes to
ASM-21. Tags `v1.0.0` and `v1.1.0` are annotated and point at verified commits.

## 1. Verify from nothing, one last time

```bash
tar -xzf blinkrate.tar.gz && cd blinkrate
./verify.sh            # isolated venv, cold install, full regeneration
./verify.sh --fast     # reuses installed numpy/pandas/scipy if memory is tight
```

`verify.sh` deletes nothing of yours. It builds a throwaway environment,
regenerates every result from the vendored EIA-861 files, runs the test suite
and the claims guard, and prints `ALL GREEN` or stops at the first failure.

To reproduce the CI byte check by hand:

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

Suggested repository description:

> How much of a US utility's reported reliability number is the measurement rule
> rather than the grid? EIA-861, 2013-2018 and 2022, eleven adversarial attacks.

Topics: `saidi`, `ieee-1366`, `electric-reliability`, `eia-861`,
`distribution-grid`, `falsification`, `reproducible-research`.

## 3. After the push

- **CI.** Open the Actions tab and confirm the first run is green. It rebuilds
  the calibration cache bit for bit, regenerates every result, fails on any byte
  difference, then runs the tests and the claims guard.
- **Release.** Create a GitHub release from tag `v1.1.0` and paste the v1.1.0
  section of CHANGELOG.md as the notes.
- **DOI (optional).** Enabling the repository in Zenodo *before* creating the
  release mints a DOI from `.zenodo.json`. Add the DOI badge to the README and
  the `doi:` field to CITATION.cff afterwards, in one commit.

## What was checked before this was written

- No absolute paths, placeholder owners, example.com addresses, or TODO markers
  in tracked files.
- Single commit author across the whole history, the attributable address above.
- Only public data: EIA Form 861, a US federal government work, plus published
  literature parameters. No utility-internal, customer or employer data anywhere
  in the tree or the history. The README's independence disclaimer is enforced by
  the claims guard.
- Bundled data licences recorded in NOTICE: EIA-861 is public domain; the three
  GitHub mirrors it was retrieved through are MIT, BSD-2-Clause, and unlicensed
  redistribution of the public-domain originals.
- Versions agree across pyproject.toml, CITATION.cff, .zenodo.json and the newest
  CHANGELOG heading, and a test fails if they drift.

## If something fails after pushing

Do not force-push over a published tag. Fix forward in a new commit, re-run
`./verify.sh`, and cut `v1.1.1`. CHANGELOG.md is where a reader looks to find out
what moved, so every correction goes there first.
