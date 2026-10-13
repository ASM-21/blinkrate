#!/usr/bin/env bash
# Replay CI on your machine. Builds a throwaway venv, rebuilds the calibration
# surface from its seed and checks it bit for bit, regenerates every number from
# the vendored data, checks the regenerated results byte for byte against the
# committed ones, then runs the tests and the claims guard. This is what a reader
# should run to check that the figures in the README come from the code rather
# than from a previous session.
#
# The venv is built in a temp dir with --copies so this works on filesystems
# without symlink support.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$(mktemp -d)/venv"
trap 'rm -rf "$(dirname "$VENV")"' EXIT

# --fast reuses the ambient scientific stack instead of downloading it. The
# isolated build is the real check; --fast exists because a cold install of
# numpy/pandas/scipy/statsmodels/matplotlib needs a few hundred MB and will be
# killed on a memory-constrained box.
FAST=""
[ "${1:-}" = "--fast" ] && FAST="--system-site-packages"

echo "==> venv at $VENV ${FAST:+(reusing system packages)}"
python3 -m venv --copies $FAST "$VENV"
# Python 3.12+ venvs ship without setuptools, and the editable install below
# builds without isolation, so its build backend has to be installed first.
"$VENV/bin/pip" install -q --upgrade pip "setuptools>=68"
"$VENV/bin/pip" install -q --no-build-isolation -e "$REPO[dev]"
PY="$VENV/bin/python"
cd "$REPO"

echo "==> calibration surface, rebuilt from its seed"
"$PY" -m blinkrate.shared.finite_sample --check

echo "==> regenerating all results"
"$PY" -m blinkrate.run_all

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "==> regenerated results against the committed ones"
  if ! git diff --exit-code --stat -- results/; then
    echo "FAIL: regenerated results differ from the committed ones (above)"
    exit 1
  fi
  echo "results/ is byte-identical to the committed results"
else
  echo "==> not a git checkout, so the byte comparison CI makes is skipped"
fi

echo "==> tests"
"$PY" -m pytest -q

echo "==> claims guard"
"$PY" tools/check_claims.py

echo "==> ALL GREEN"
