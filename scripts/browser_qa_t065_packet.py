"""Open the actual T065 packet in Edge without creating annotation state."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import socket
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path

from playwright.sync_api import sync_playwright

from abrex.literature import serve_review


def _serve(packet: str, state: str, lock: str, port: int) -> None:
    serve_review(
        Path(packet),
        host="127.0.0.1",
        port=port,
        state_path=Path(state),
        lock_path=Path(lock),
        workflow_name="T065 actual-packet QA",
        mode="blind",
    )


def _port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def run(packet: Path, output: Path) -> dict[str, object]:
    """Load the real packet and verify its UI/API without saving a decision."""

    with tempfile.TemporaryDirectory(prefix="abrex-t065-browser-") as temporary:
        root = Path(temporary)
        state = root / "annotations.json"
        lock = root / "annotations.lock.json"
        port = _port()
        process = multiprocessing.get_context("spawn").Process(
            target=_serve,
            args=(str(packet), str(state), str(lock), port),
        )
        process.start()
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "T065 blind reviewer did not start"
                        ) from None
                    time.sleep(0.05)
            url = f"http://127.0.0.1:{port}/"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url)
                page.locator("#passage").wait_for()
                payload = page.request.get(url + "api/packet").json()
                keys = _keys(payload)
                forbidden = {
                    "suggestions",
                    "method_ids",
                    "method_diagnostics",
                    "confidence",
                    "prediction",
                    "candidate",
                }
                leaked = sorted(keys & forbidden)
                if leaked:
                    raise AssertionError(f"T065 payload leaked fields: {leaked}")
                case_count = len(payload["cases"])
                visible_passage = page.locator("#passage").is_visible()
                add_control = page.get_by_text("Add relation", exact=True).is_visible()
                article = page.locator("main.panel")
                annotation = page.locator(".app > aside.panel").last
                pane_styles = {
                    "article": article.evaluate(
                        "el => ({overflowY:getComputedStyle(el).overflowY, "
                        "clientHeight:el.clientHeight,scrollHeight:el.scrollHeight})"
                    ),
                    "annotation": annotation.evaluate(
                        "el => ({overflowY:getComputedStyle(el).overflowY, "
                        "clientHeight:el.clientHeight,scrollHeight:el.scrollHeight})"
                    ),
                }
                annotation_start = annotation.evaluate("el => el.scrollTop")
                article.evaluate("el => {el.scrollTop = 240}")
                article_position = article.evaluate("el => el.scrollTop")
                annotation_after_article = annotation.evaluate("el => el.scrollTop")
                annotation.evaluate("el => {el.scrollTop = 240}")
                annotation_position = annotation.evaluate("el => el.scrollTop")
                article_after_annotation = article.evaluate("el => el.scrollTop")
                independent_scroll = bool(
                    pane_styles["article"]["overflowY"] == "auto"
                    and pane_styles["annotation"]["overflowY"] == "auto"
                    and article_position > 0
                    and annotation_position > annotation_start
                    and annotation_after_article == annotation_start
                    and article_after_annotation == article_position
                )
                if not independent_scroll:
                    raise AssertionError(
                        "article and annotation panes do not scroll independently"
                    )
                browser.close()
            if state.exists() or lock.exists():
                raise AssertionError("read-only QA created annotation or lock state")
            result = {
                "schema_version": "t065-browser-qa-v1",
                "status": "passed",
                "browser": "Microsoft Edge via Playwright",
                "packet_id": payload["packet_id"],
                "cases": case_count,
                "checks": {
                    "actual_packet_loaded": visible_passage,
                    "source_payload_isolated": not leaked,
                    "from_scratch_relation_control": add_control,
                    "independent_article_and_annotation_scroll": independent_scroll,
                    "no_annotation_state_created": True,
                },
            }
        finally:
            process.terminate()
            process.join(timeout=5)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet",
        type=Path,
        default=Path("evidence/T065/review-packet-blind-v1.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/artifacts/T065-browser-qa.json")
    )
    args = parser.parse_args()
    print(json.dumps(run(args.packet, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
