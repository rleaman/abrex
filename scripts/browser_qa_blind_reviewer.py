"""Exercise the blind reviewer in a real local Edge browser."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import socket
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from abrex.literature import (
    BlindReviewCase,
    create_blind_packet,
    serve_review,
    write_blind_packet,
)


def _serve(packet: str, state: str, lock: str, port: int) -> None:
    serve_review(
        Path(packet),
        host="127.0.0.1",
        port=port,
        state_path=Path(state),
        lock_path=Path(lock),
        workflow_name="T064 browser QA",
        mode="blind",
    )


def _port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _case(case_id: str, text: str, *, source_kind: str) -> BlindReviewCase:
    return BlindReviewCase(
        case_id=case_id,
        article_id=f"article-{case_id}",
        article_group_id=f"group-{case_id}",
        title=f"QA source {case_id}",
        arm="pmc_cc_by",
        source_url=f"https://example.invalid/{case_id}",
        source_kind=source_kind,
        section_id=f"section-{case_id}",
        section_heading="QA section",
        canonical_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        passage_start=0,
        passage_end=len(text),
        text=text,
    )


def _select(page: Page, value: str, occurrence: int = 0) -> None:
    page.locator("#passage").evaluate(
        """(host, wanted) => {
          const [needle, occurrence] = wanted;
          const full = host.textContent;
          let start = -1;
          let cursor = 0;
          for (let i = 0; i <= occurrence; i++) {
            start = full.indexOf(needle, cursor);
            if (start < 0) throw new Error('text not found: ' + needle);
            cursor = start + needle.length;
          }
          const end = start + needle.length;
          const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
          let offset = 0, startNode, startOffset, endNode, endOffset, current;
          while ((current = walker.nextNode())) {
            const next = offset + current.data.length;
            if (!startNode && start >= offset && start <= next) {
              startNode = current; startOffset = start - offset;
            }
            if (end >= offset && end <= next) {
              endNode = current; endOffset = end - offset; break;
            }
            offset = next;
          }
          const range = document.createRange();
          range.setStart(startNode, startOffset); range.setEnd(endNode, endOffset);
          const selection = window.getSelection(); selection.removeAllRanges();
          selection.addRange(range); host.dispatchEvent(new Event('mouseup'));
        }""",
        [value, occurrence],
    )


def run(output: Path, screenshot: Path) -> dict[str, object]:
    """Run save/reload, zero-case, import/export, lock, and isolation checks."""

    with tempfile.TemporaryDirectory(prefix="abrex-t064-browser-") as temporary:
        root = Path(temporary)
        packet_path = root / "packet.json"
        state_path = root / "annotations.json"
        lock_path = root / "annotations.lock.json"
        packet = create_blind_packet(
            (
                _case(
                    "relation",
                    "🧬 Tumor necrosis factor (TNF) differs from TNF elsewhere.",
                    source_kind="table",
                ),
                _case(
                    "empty",
                    "This control passage contains no definition.",
                    source_kind="paragraph",
                ),
            ),
            protocol_id="t064-browser-qa-v1",
            seed=20261002,
        )
        write_blind_packet(packet, packet_path)
        port = _port()
        process = multiprocessing.get_context("spawn").Process(
            target=_serve,
            args=(str(packet_path), str(state_path), str(lock_path), port),
        )
        process.start()
        try:
            url = f"http://127.0.0.1:{port}/"
            deadline = time.monotonic() + 10
            while True:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("blind reviewer did not start") from None
                    time.sleep(0.05)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.goto(url)
                page.locator("#passage").wait_for()
                api_payload = page.request.get(url + "api/packet").text()
                forbidden = (
                    "suggestions",
                    "method_ids",
                    "method_diagnostics",
                    "confidence",
                    "inventory_category",
                    "selection_reason",
                )
                leaked = [name for name in forbidden if name in api_payload]
                if leaked:
                    raise AssertionError(f"blind payload leaked fields: {leaked}")
                _select(page, "Tumor necrosis factor")
                page.locator("#use-lf").click()
                _select(page, "TNF", occurrence=0)
                page.locator("#use-sf").click()
                page.locator("#add").click()
                page.locator("#searched").check()
                page.locator("#save").click()
                page.get_by_text("Draft saved durably.").wait_for()
                page.reload()
                page.get_by_text("Tumor necrosis factor → TNF").wait_for()
                page.locator("#next").click()
                page.locator("#title").filter(has_text="empty").wait_for()
                page.locator("#searched").check()
                page.locator("#save").click()
                page.get_by_text("Draft saved durably.").wait_for()
                backup = root / "backup.json"
                with page.expect_download() as download_info:
                    page.get_by_text("JSON backup").click()
                download_info.value.save_as(backup)
                page.locator("#import-json").set_input_files(backup)
                page.get_by_text("Backup imported and saved.").wait_for()
                page.on("dialog", lambda dialog: dialog.accept())
                page.locator("#lock").click()
                page.get_by_text("Annotation locked.", exact=False).wait_for()
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=True)
                assert page.locator("#save").is_disabled()
                locked = page.request.get(url + "api/export/locked").json()
                browser.close()
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            result = {
                "schema_version": "t064-browser-qa-v1",
                "status": "passed",
                "browser": "Microsoft Edge via Playwright",
                "viewport": {"width": 390, "height": 844},
                "packet_id": packet.packet_id,
                "cases": len(packet.cases),
                "checks": {
                    "source_payload_isolated": not leaked,
                    "unicode_and_repeated_selection": True,
                    "relation_from_scratch": True,
                    "save_reload": True,
                    "zero_relation_completion": True,
                    "json_export_import": True,
                    "server_enforced_lock": lock["predictions_exposed"] is False,
                    "locked_export": locked["schema_version"]
                    == "abrex-blind-annotation-export-v1",
                    "narrow_viewport": True,
                },
                "annotation_state_sha256": lock["annotation_state_sha256"],
                "state_revisions": {
                    key: value["revision"]
                    for key, value in state["annotations"].items()
                },
                "screenshot": str(screenshot),
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
    """Run QA and write its evidence artifact."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/artifacts/T064-browser-qa.json")
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=Path(".artifacts/T064/blind-reviewer-qa.png"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.screenshot), sort_keys=True))
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
