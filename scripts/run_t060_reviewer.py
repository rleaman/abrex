"""Run the assisted T060 output reviewer with repository defaults."""

from __future__ import annotations

import argparse
from pathlib import Path

from abrex.literature import serve_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = Path(__file__).parents[1]
    serve_review(
        root / "evidence/T060/review-packet.json",
        host=args.host,
        port=args.port,
        workflow_name="T061 assisted development-output review",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
