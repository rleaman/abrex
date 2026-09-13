"""Materialize the frozen T057 development views."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abrex.literature.development_views import build_development_views  # noqa: E402


def main() -> int:
    build_development_views(
        ROOT / "evidence/T052/review-packet-v2.json",
        ROOT / "evidence/T052/review-packet-v2.annotations.final.json",
        ROOT / "evidence/T052/review-packet-v2.annotations.json",
        ROOT / "evidence/T057/accepted-mechanical-corrections.json",
        ROOT / "evidence/T053/inventory.json",
        ROOT / "evidence/T053/audit-packet.json",
        ROOT / "docs/annotation-guidelines/2026-09-12-development-supplement-v1.md",
        ROOT / "docs/scientific-model/2026-09-12-development-challenge.md",
        ROOT / "evidence/T057",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
