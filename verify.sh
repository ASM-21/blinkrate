#!/usr/bin/env bash
# Build a throwaway venv, regenerate every number from the vendored data, run the
# tests and the claims guard. This is what a reader should run to check that the
# figures in the README come from the code rather than from a previous session.
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
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q --no-build-isolation -e "$REPO[dev]"

echo "==> regenerating all results"
(cd "$REPO" && "$VENV/bin/python" -m blinkrate.run_all)

echo "==> tests"
(cd "$REPO" && "$VENV/bin/python" -m pytest -q)

echo "==> claims guard"
(cd "$REPO" && "$VENV/bin/python" tools/check_claims.py)

echo "==> ALL GREEN"
