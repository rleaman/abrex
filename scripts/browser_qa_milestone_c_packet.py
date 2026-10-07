"""Exercise the actual Milestone C packet with disposable browser state."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import socket
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path

from playwright.sync_api import sync_playwright

from abrex.literature import read_blind_packet, serve_review

ROOT_KEYS = {
    "schema_version",
    "packet_id",
    "content_sha256",
    "protocol_id",
    "seed",
    "cases",
    "_workflow",
}
CASE_KEYS = {
    "case_id",
    "article_id",
    "article_group_id",
    "title",
    "arm",
    "source_url",
    "source_kind",
    "section_id",
    "section_heading",
    "canonical_text_sha256",
    "passage_start",
    "passage_end",
    "text",
    "context_before",
    "context_after",
    "structures",
}
STRUCTURE_KEYS = {"kind", "text", "source_path"}


def _serve(packet: str, state: str, lock: str, port: int) -> None:
    serve_review(
        Path(packet),
        host="127.0.0.1",
        port=port,
        state_path=Path(state),
        lock_path=Path(lock),
        workflow_name="Milestone C prediction-blind review",
        mode="blind",
    )


def _port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_payload_schema(payload: Mapping[str, object]) -> None:
    unexpected_root = set(payload) - ROOT_KEYS
    if unexpected_root:
        raise AssertionError(f"unexpected blind packet keys: {unexpected_root}")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise AssertionError("blind packet cases are absent")
    for case in cases:
        if not isinstance(case, Mapping):
            raise AssertionError("blind packet case is not an object")
        unexpected_case = set(case) - CASE_KEYS
        if unexpected_case:
            raise AssertionError(f"unexpected blind case keys: {unexpected_case}")
        structures = case.get("structures")
        if not isinstance(structures, list):
            raise AssertionError("blind case structures are not an array")
        for structure in structures:
            if not isinstance(structure, Mapping):
                raise AssertionError("blind structure is not an object")
            unexpected_structure = set(structure) - STRUCTURE_KEYS
            if unexpected_structure:
                raise AssertionError(
                    f"unexpected blind structure keys: {unexpected_structure}"
                )


def run(
    packet_path: Path,
    state_path: Path,
    output: Path,
    *,
    expected_cases: int = 120,
) -> dict[str, object]:
    """Validate actual-packet loading, isolation, persistence, and lock rejection."""

    packet = read_blind_packet(packet_path)
    authoritative_before = _sha(state_path)
    with tempfile.TemporaryDirectory(prefix="abrex-milestone-c-browser-") as temporary:
        root = Path(temporary)
        state = root / "annotations.json"
        lock = root / "annotations.lock.json"
        port = _port()
        process = multiprocessing.get_context("spawn").Process(
            target=_serve,
            args=(str(packet_path), str(state), str(lock), port),
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
                            "Milestone C reviewer did not start"
                        ) from None
                    time.sleep(0.05)
            url = f"http://127.0.0.1:{port}/"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url)
                page.locator("#passage").wait_for()
                payload = page.request.get(url + "api/packet").json()
                if not isinstance(payload, Mapping):
                    raise AssertionError("blind packet API did not return an object")
                _assert_payload_schema(payload)
                cases = payload["cases"]
                if not isinstance(cases, list) or len(cases) != expected_cases:
                    raise AssertionError(
                        f"actual packet does not contain {expected_cases} cases"
                    )
                if page.locator("#case-list .case").count() != expected_cases:
                    raise AssertionError(
                        f"reviewer did not list all {expected_cases} passages"
                    )
                positions = []
                for index in (0, (expected_cases - 1) // 2, expected_cases - 1):
                    page.locator("#case-list .case").nth(index).click()
                    expected = f"{index + 1} of {expected_cases}"
                    page.locator("#position").filter(has_text=expected).wait_for()
                    positions.append(expected)
                page.locator("#case-list .case").nth(0).click()
                defaults = {
                    "relation_kind": page.locator("#kind").input_value(),
                    "evidence_structure": page.locator("#evidence").input_value(),
                    "context_requirement": page.locator(
                        "#required-context"
                    ).input_value(),
                }
                expected_defaults = {
                    "relation_kind": "abbreviation_expansion",
                    "evidence_structure": "contiguous_shared",
                    "context_requirement": "text_alone",
                }
                if defaults != expected_defaults:
                    raise AssertionError(
                        f"unexpected new-relation defaults: {defaults}"
                    )
                page.locator("#shortcut-help").click()
                page.locator("#shortcut-dialog").filter(
                    has_text="Ctrl+Shift+Enter"
                ).wait_for()
                page.locator("#shortcut-close").click()
                page.keyboard.press("Control+Enter")
                page.locator("#save-status").filter(
                    has_text="Both exact endpoints are required."
                ).wait_for()
                page.keyboard.press("Control+Shift+C")
                if not page.locator("#searched").is_checked():
                    raise AssertionError("completion shortcut did not mark the passage")
                page.keyboard.press("Control+Shift+Enter")
                page.locator("#progress").filter(has_text="1 complete").wait_for()
                page.locator("#position").filter(
                    has_text=f"2 of {expected_cases}"
                ).wait_for()
                page.reload()
                page.locator("#progress").filter(has_text="1 complete").wait_for()
                backup = root / "backup.json"
                with page.expect_download() as download_info:
                    page.get_by_text("JSON backup").click()
                download_info.value.save_as(backup)
                page.locator("#import-json").set_input_files(backup)
                page.get_by_text("Backup imported and saved.").wait_for()
                page.on("dialog", lambda dialog: dialog.accept())
                page.locator("#lock").click()
                page.locator("#save-status").filter(has_text="Lock failed").wait_for()
                readiness = page.request.get(url + "api/readiness").json()
                lock_rejected = readiness["remaining_cases"] == expected_cases - 1
                if not lock_rejected:
                    raise AssertionError(
                        "incomplete lock rejection returned an unexpected "
                        "remaining-case count"
                    )
                browser.close()
            if lock.exists():
                raise AssertionError("incomplete disposable review created a lock")
            if not state.is_file():
                raise AssertionError("disposable save did not persist state")
            result = {
                "schema_version": "campaign-2026-10-milestone-c-browser-qa-v1",
                "status": "passed",
                "browser": "Microsoft Edge via Playwright",
                "packet_id": packet.packet_id,
                "cases": len(packet.cases),
                "checks": {
                    "actual_packet_loaded": True,
                    "all_expected_passages_listed": True,
                    "first_middle_last_navigation": positions,
                    "strict_payload_allowlist": True,
                    "common_relation_defaults": defaults,
                    "shortcut_help_dialog": True,
                    "add_relation_shortcut": True,
                    "mark_complete_shortcut": True,
                    "save_and_next_shortcut": True,
                    "disposable_save_reload": True,
                    "json_export_import": True,
                    "incomplete_lock_rejected": lock_rejected,
                    "no_disposable_lock_created": True,
                    "authoritative_state_unchanged": _sha(state_path)
                    == authoritative_before,
                },
                "authoritative_state_sha256": authoritative_before,
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
        default=Path(
            "evidence/campaign-2026-10/milestone-c/review-packet-blind-v1.json"
        ),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/"
            "review-packet-blind-v1.annotations.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/actual-packet-browser-qa-v1.json"
        ),
    )
    parser.add_argument("--expected-cases", type=int, default=120)
    args = parser.parse_args()
    result = run(
        args.packet,
        args.state,
        args.output,
        expected_cases=args.expected_cases,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
