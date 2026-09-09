"""Run the local T052 browser reviewer."""

from __future__ import annotations

import argparse
from pathlib import Path

from abrex.literature import serve_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve_review(args.packet, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
