"""Run the local prediction-blind ABREX annotation interface."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

from abrex.literature import read_blind_packet, serve_review


def main() -> int:
    """Validate a blind packet and serve it until interrupted."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    packet = read_blind_packet(args.packet)
    state = args.state or args.packet.with_name(f"{args.packet.stem}.annotations.json")
    lock = args.lock or state.with_name(f"{state.stem}.lock.json")
    print(f"Packet: {packet.packet_id} ({len(packet.cases)} passages)")
    print(f"Draft state: {state.resolve()}")
    print(f"Lock file: {lock.resolve()}")
    url = f"http://{args.host}:{args.port}/"
    print(f"Reviewer: {url}")
    if not args.no_open:
        threading.Timer(0.7, webbrowser.open, args=(url,)).start()
    serve_review(
        args.packet,
        host=args.host,
        port=args.port,
        state_path=state,
        lock_path=lock,
        workflow_name="ABREX prediction-blind annotation",
        mode="blind",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
