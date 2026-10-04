"""Open or verify the corrected T061 assisted development-output review."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

from abrex.literature.review import serve_review
from abrex.literature.review_interchange import read_annotation_state
from abrex.literature.review_packet import read_review_packet
from abrex.literature.review_readiness import review_readiness

ROOT = Path(__file__).parents[1]
DEFAULT_PACKET = ROOT / "evidence/T060/review-packet-split-v2.json"


def readiness_report(packet_path: Path, state_path: Path) -> tuple[bool, str]:
    """Return completeness and a concise report for every T061 passage."""

    packet = read_review_packet(packet_path)
    state = read_annotation_state(packet, state_path)
    required = tuple(case.case_id for case in packet.cases)
    result = review_readiness(packet, state, required)
    lines = [
        f"Working file: {state_path}",
        (
            f"Progress: {result.complete_cases}/{result.required_cases} passages "
            f"complete; {result.remaining_items} required decisions remain."
        ),
    ]
    if result.complete:
        lines.append("READY: the T061 assisted review is complete.")
    else:
        lines.append("NOT READY: reopen these passages with Needs attention:")
        lines.extend(
            f"- {case.title} ({len(case.issues)} items)"
            for case in result.cases
            if not case.complete
        )
    return result.complete, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--check", action="store_true", help="report what remains")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument(
        "--packet",
        type=Path,
        default=DEFAULT_PACKET,
    )
    args = parser.parse_args()
    packet_path = args.packet if args.packet.is_absolute() else ROOT / args.packet
    state_path = packet_path.with_suffix(".annotations.json")
    complete, report = readiness_report(packet_path, state_path)
    print(report)
    if args.check:
        return 0 if complete else 1
    url = f"http://{args.host}:{args.port}/"
    print(f"\nOpening the reviewer at {url}")
    print("Keep this window open. Press Ctrl+C here when you want to pause.")
    if not args.no_open:
        threading.Timer(0.7, webbrowser.open, args=(url,)).start()
    packet = read_review_packet(packet_path)
    serve_review(
        packet_path,
        host=args.host,
        port=args.port,
        state_path=state_path,
        required_case_ids=tuple(case.case_id for case in packet.cases),
        workflow_name="T061 assisted development-output review",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
