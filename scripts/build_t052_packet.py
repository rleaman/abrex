"""Build the deterministic T052 packet and BioC interchange file."""

from __future__ import annotations

import argparse
from pathlib import Path

from abrex.literature import build_review_packet, write_bioc_xml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--bioc", type=Path, required=True)
    args = parser.parse_args()
    packet = build_review_packet(args.manifest, args.packet)
    write_bioc_xml(packet, args.bioc)
    print(f"packet={args.packet} cases={len(packet.cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
