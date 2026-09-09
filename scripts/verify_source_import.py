"""Verify that ``abrex`` imports from the requested source checkout."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path


def verify_source_import(root: Path) -> Path:
    """Return the imported package path after checking its source identity."""
    import abrex

    if abrex.__file__ is None:
        raise RuntimeError("abrex has no importable package file")
    origin = Path(abrex.__file__).resolve()
    expected = (root / "src" / "abrex").resolve()
    if not origin.is_relative_to(expected):
        raise RuntimeError(f"expected abrex below {expected}, imported {origin}")
    return origin


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the checkout root, verify the import, and print its exact origin."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        origin = verify_source_import(args.root)
    except RuntimeError as error:
        print(f"source import verification failed: {error}", file=sys.stderr)
        return 1
    print(f"verified source package: {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
