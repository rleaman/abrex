"""Export the pinned CellLiteraturePipeline abbreviation annotation snapshot."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from abrex.corpora.adapters.clp_snapshot import export_clp_snapshot


def main(argv: Sequence[str] | None = None) -> int:
    """Export a compact derivative without importing the sister package."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--evaluation-summary", type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = export_clp_snapshot(
        items_path=args.items,
        annotations_path=args.annotations,
        output_path=args.output,
        manifest_path=args.manifest,
        source_commit=args.source_commit,
        evaluation_summary_path=args.evaluation_summary,
    )
    print(json.dumps(manifest["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
