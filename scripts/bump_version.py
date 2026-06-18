#!/usr/bin/env python3
"""Bump the ``zedgi`` package to the next publishable version.

Reads the latest version published to PyPI, computes the next one with the
capped-digit scheme (each of major.minor.patch is 0-9, carrying on overflow:
1.0.0 -> 1.0.1 -> ... -> 1.0.9 -> 1.1.0 -> ... -> 1.9.9 -> 2.0.0), then writes
it to the two spots that must stay in sync:
    - zedgi/_version.py   __version__
    - pyproject.toml      version

Run before publishing so ``twine upload`` never fails on an existing version:
    python3 scripts/bump_version.py
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

PKG_NAME = "zedgi"
PKG_DIR = Path(__file__).resolve().parent.parent
VERSION_PY = PKG_DIR / "zedgi" / "_version.py"
PYPROJECT = PKG_DIR / "pyproject.toml"


def next_version(version: str) -> str:
    """``a.b.c`` -> next version, capping each component at 9 and carrying over."""
    try:
        a, b, c = (int(part) for part in version.split("."))
    except ValueError as exc:
        raise SystemExit(f'Cannot parse version "{version}" as major.minor.patch') from exc
    c += 1
    if c > 9:
        c, b = 0, b + 1
    if b > 9:
        b, a = 0, a + 1
    return f"{a}.{b}.{c}"


def published_version(name: str) -> str | None:
    """Highest version published to PyPI, or None if never published.

    Uses the full ``releases`` map and takes the max — ``info.version`` is served
    inconsistently across PyPI's CDN edges, so relying on it can flap between
    releases and break idempotency.
    """
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # not published yet
        raise
    triples = [
        tuple(int(p) for p in v.split("."))
        for v in data.get("releases", {})
        if re.fullmatch(r"\d+\.\d+\.\d+", v)
    ]
    if not triples:
        return None
    a, b, c = max(triples)
    return f"{a}.{b}.{c}"


def _cmp(x: str, y: str) -> int:
    xs = [int(n) for n in x.split(".")]
    ys = [int(n) for n in y.split(".")]
    return (xs > ys) - (xs < ys)


def read_local() -> str:
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', VERSION_PY.read_text())
    if not match:
        raise SystemExit(f"Could not find __version__ in {VERSION_PY}")
    return match.group(1)


def write_version(path: Path, pattern: str, target: str) -> None:
    text = path.read_text()
    updated, count = re.subn(pattern, rf'\g<1>{target}\g<2>', text, count=1, flags=re.MULTILINE)
    if count == 0:
        raise SystemExit(f"Could not find version field in {path}")
    path.write_text(updated)


def main() -> None:
    local = read_local()
    published = published_version(PKG_NAME)

    # First publish: keep whatever the files already declare. Otherwise bump past
    # the published version, but never below a locally-staged-ahead version.
    if published is None:
        target = local
    else:
        bumped = next_version(published)
        target = local if _cmp(local, bumped) > 0 else bumped

    write_version(VERSION_PY, r'(__version__\s*=\s*["\'])[^"\']*(["\'])', target)
    write_version(PYPROJECT, r'(^version\s*=\s*["\'])[^"\']*(["\'])', target)

    print(f"{PKG_NAME}: {published or '(unpublished)'} -> {target}")


if __name__ == "__main__":
    main()
