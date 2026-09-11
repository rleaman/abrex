"""Materialize the frozen T052 inputs into the T053 audit artifacts."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abrex.literature.audit_inventory import build_audit_inventory  # noqa: E402


def main() -> int:
    build_audit_inventory(
        ROOT / "evidence/T052/review-packet-v2.json",
        ROOT / "evidence/T052/review-packet-v2.annotations.final.json",
        ROOT / "evidence/T052/manifest.json",
        ROOT / "evidence/T053",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
