#!/usr/bin/env bash
# One-shot release for the `zedgi` PyPI package: bump → build tooling → build →
# validate → upload. Run from anywhere; it cd's to the package root itself.
#
#   ./scripts/release.sh              # upload to real PyPI
#   ./scripts/release.sh --test       # upload to TestPyPI instead
set -euo pipefail

cd "$(dirname "$0")/.."

repo="pypi"
[ "${1:-}" = "--test" ] && repo="testpypi"

python3 scripts/bump_version.py

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python3 -m pip install --upgrade build twine

rm -rf dist build
python3 -m build
python3 -m twine check dist/*

if [ "$repo" = "testpypi" ]; then
  python3 -m twine upload --repository testpypi dist/*
else
  python3 -m twine upload dist/*
fi

deactivate
