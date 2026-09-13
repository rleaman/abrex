"""Open or verify the bounded T057 human policy review."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abrex.literature.review import serve_review  # noqa: E402
from abrex.literature.review_interchange import read_annotation_state  # noqa: E402
from abrex.literature.review_packet import read_review_packet  # noqa: E402
from abrex.literature.review_readiness import (  # noqa: E402
    ReviewReadiness,
    readiness_text,
    required_case_ids_from_t053,
    review_readiness,
)

PACKET = ROOT / "evidence/T052/review-packet-v2.json"
WORKING_FILE = ROOT / "evidence/T052/review-packet-v2.annotations.json"
INVENTORY = ROOT / "evidence/T053/inventory.json"


def current_readiness() -> tuple[ReviewReadiness, str]:
    packet = read_review_packet(PACKET)
    state = read_annotation_state(packet, WORKING_FILE)
    required = required_case_ids_from_t053(INVENTORY)
    result = review_readiness(packet, state, required)
    return result, readiness_text(result, WORKING_FILE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review only the 20 passages required to finish T057."
    )
    parser.add_argument("--check", action="store_true", help="report what remains")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    result, report = current_readiness()
    print(report)
    if args.check:
        return 0 if result.complete else 1
    url = f"http://{args.host}:{args.port}/"
    print(f"\nOpening the reviewer at {url}")
    print("Keep this window open. Press Ctrl+C here when you want to pause.")
    if not args.no_open:
        threading.Timer(0.7, webbrowser.open, args=(url,)).start()
    serve_review(
        PACKET,
        host=args.host,
        port=args.port,
        state_path=WORKING_FILE,
        required_case_ids=required_case_ids_from_t053(INVENTORY),
        workflow_name="Finish the T057 policy review",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
