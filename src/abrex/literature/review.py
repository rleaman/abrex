"""Public T052 reviewer facade and small local HTTP application."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from abrex.literature.blind_review import (
    BlindAnnotationLock,
    BlindReviewPacket,
    blind_review_readiness,
    create_annotation_lock,
    read_blind_packet,
    write_annotation_lock,
)
from abrex.literature.blind_reviewer_ui import BLIND_REVIEWER_HTML
from abrex.literature.review_interchange import (
    import_bioc_xml,
    read_annotation_state,
    write_annotation_state,
    write_bioc_xml,
)
from abrex.literature.review_models import (
    AnnotationState,
    AnnotationSubmission,
    ReviewCase,
    ReviewError,
    ReviewPacket,
    ReviewSpan,
    apply_submission,
    fingerprint,
    validate_annotation_state,
)
from abrex.literature.review_packet import (
    build_review_fixture,
    build_review_packet,
    read_review_packet,
)
from abrex.literature.review_readiness import review_readiness
from abrex.literature.reviewer_ui import REVIEWER_HTML

# Kept as a deliberately small compatibility surface for the package facade.
REVIEW_SCHEMA_VERSION = "t052-review-packet-v2"
ReviewDecision = object


class _ReviewerState:
    def __init__(
        self,
        packet_path: Path,
        *,
        state_path: Path | None = None,
        required_case_ids: tuple[str, ...] | None = None,
        workflow_name: str | None = None,
        mode: Literal["assisted", "blind"] = "assisted",
        lock_path: Path | None = None,
    ) -> None:
        self.packet_path = packet_path
        self.mode = mode
        self.blind_packet: BlindReviewPacket | None = None
        if mode == "blind":
            self.blind_packet = read_blind_packet(packet_path)
            self.packet = self.blind_packet.annotation_packet()
        else:
            self.packet = read_review_packet(packet_path)
        # Keep annotation backups content-addressed to the packet filename so
        # a corrected packet cannot accidentally load the legacy packet's
        # state.  A packet/content mismatch is still rejected by the state
        # validator when a sidecar is deliberately copied into this location.
        self.state_path = state_path or packet_path.with_name(
            f"{packet_path.stem}.annotations.json"
        )
        available = {case.case_id for case in self.packet.cases}
        self.required_case_ids = required_case_ids or tuple(
            case.case_id for case in self.packet.cases
        )
        unknown = sorted(set(self.required_case_ids) - available)
        if unknown:
            raise ReviewError(f"unknown required reviewer cases: {unknown}")
        self.workflow_name = workflow_name or "Review packet"
        self.lock_path = lock_path or self.state_path.with_name(
            f"{self.state_path.stem}.lock.json"
        )
        self.lock = threading.RLock()
        self.state = read_annotation_state(self.packet, self.state_path)
        self.annotation_lock = self._read_lock()

    def packet_payload(self) -> dict[str, object]:
        if self.blind_packet is not None:
            payload = self.blind_packet.model_dump(mode="json")
        else:
            payload = self.packet.model_dump(mode="json")
        required = set(self.required_case_ids)
        payload["cases"] = [
            case for case in payload["cases"] if case["case_id"] in required
        ]
        payload["_workflow"] = {
            "name": self.workflow_name,
            "working_file": str(self.state_path.resolve()),
            "required_cases": len(self.required_case_ids),
            "mode": self.mode,
        }
        return payload

    def readiness_payload(self) -> dict[str, object]:
        value = (
            blind_review_readiness(self.packet, self.state, self.required_case_ids)
            if self.mode == "blind"
            else review_readiness(self.packet, self.state, self.required_case_ids)
        )
        return {
            **value.model_dump(mode="json"),
            "working_file": str(self.state_path.resolve()),
        }

    def save_submission(self, payload: bytes) -> AnnotationState:
        self._require_unlocked()
        try:
            submission = AnnotationSubmission.model_validate_json(payload)
        except ValueError as error:
            raise ReviewError(f"invalid annotation submission: {error}") from error
        with self.lock:
            updated = apply_submission(self.packet, self.state, submission)
            write_annotation_state(updated, self.state_path)
            self.state = updated
            return updated

    def import_json(self, payload: bytes) -> AnnotationState:
        self._require_unlocked()
        try:
            value = json.loads(payload)
            if (
                isinstance(value, dict)
                and value.get("schema_version") == "t052-annotations-v2"
            ):
                imported = AnnotationState.model_validate(value)
                validate_annotation_state(self.packet, imported)
                with self.lock:
                    write_annotation_state(imported, self.state_path)
                    self.state = imported
                    return imported
            return self.save_submission(payload)
        except (json.JSONDecodeError, ValueError) as error:
            if isinstance(error, ReviewError):
                raise
            raise ReviewError(f"invalid JSON annotation backup: {error}") from error

    def lock_payload(self) -> dict[str, object]:
        """Return the public lock status without mutating annotation state."""

        if self.annotation_lock is None:
            return {"locked": False, "mode": self.mode}
        return {
            "locked": True,
            "mode": self.mode,
            **self.annotation_lock.model_dump(mode="json"),
        }

    def lock_annotations(self) -> dict[str, object]:
        """Lock a complete prediction-blind state and prevent later mutation."""

        if self.mode != "blind":
            raise ReviewError("annotation locking is available only in blind mode")
        with self.lock:
            if self.annotation_lock is not None:
                return self.lock_payload()
            readiness = blind_review_readiness(
                self.packet, self.state, self.required_case_ids
            )
            if not readiness.complete:
                raise ReviewError(
                    "annotation is not ready to lock: "
                    f"{readiness.remaining_cases} passages remain"
                )
            self.annotation_lock = create_annotation_lock(self.packet, self.state)
            write_annotation_lock(self.annotation_lock, self.lock_path)
            return self.lock_payload()

    def locked_export(self) -> dict[str, object]:
        """Return the immutable lock and exact state it binds."""

        if self.annotation_lock is None:
            raise ReviewError("annotation state has not been locked")
        return {
            "schema_version": "abrex-blind-annotation-export-v1",
            "lock": self.annotation_lock.model_dump(mode="json"),
            "annotation_state": self.state.model_dump(mode="json"),
        }

    def _require_unlocked(self) -> None:
        if self.annotation_lock is not None:
            raise ReviewError(
                "annotation state is locked; create a new version to edit"
            )

    def _read_lock(self) -> BlindAnnotationLock | None:
        if not self.lock_path.is_file():
            return None
        try:
            value = BlindAnnotationLock.model_validate_json(
                self.lock_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValueError) as error:
            raise ReviewError(f"invalid annotation lock: {error}") from error
        if (
            value.packet_id != self.packet.packet_id
            or value.packet_content_sha256 != self.packet.content_sha256
            or value.annotation_state_sha256
            != fingerprint(self.state.model_dump(mode="json"))
        ):
            raise ReviewError("annotation lock does not match packet and state")
        return value


def _json(handler: BaseHTTPRequestHandler, value: object, status: int = 200) -> None:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def serve_review(
    packet_path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    state_path: Path | None = None,
    required_case_ids: tuple[str, ...] | None = None,
    workflow_name: str | None = None,
    mode: Literal["assisted", "blind"] = "assisted",
    lock_path: Path | None = None,
) -> None:
    """Serve a packet until interrupted. State is persisted beside the packet."""
    app = _ReviewerState(
        Path(packet_path),
        state_path=state_path,
        required_case_ids=required_case_ids,
        workflow_name=workflow_name,
        mode=mode,
        lock_path=lock_path,
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/":
                body = (
                    BLIND_REVIEWER_HTML if app.mode == "blind" else REVIEWER_HTML
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif route == "/api/packet":
                _json(self, app.packet_payload())
            elif route == "/api/annotations":
                _json(self, app.state.model_dump(mode="json"))
            elif route == "/api/readiness":
                _json(self, app.readiness_payload())
            elif route == "/api/lock":
                _json(self, app.lock_payload())
            elif route == "/api/export/json":
                body = app.state.model_dump_json(indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="review-packet.annotations.json"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif route == "/api/export/bioc":
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as temp:
                    path = Path(temp.name)
                try:
                    write_bioc_xml(app.packet, path, app.state)
                    body = path.read_bytes()
                finally:
                    path.unlink(missing_ok=True)
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="review-packet.bioc.xml"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif route == "/api/export/locked":
                try:
                    body = (
                        json.dumps(
                            app.locked_export(),
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("utf-8")
                except ReviewError as error:
                    _json(self, {"error": str(error)}, 400)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="blind-annotations.locked.json"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                _json(self, {"error": "not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            try:
                if route == "/api/annotations":
                    value = app.save_submission(payload)
                elif route == "/api/import/json":
                    value = app.import_json(payload)
                elif route == "/api/import/bioc" and app.mode == "assisted":
                    with app.lock:
                        value = import_bioc_xml(app.packet, payload, app.state)
                        write_annotation_state(value, app.state_path)
                        app.state = value
                elif route == "/api/lock":
                    _json(self, app.lock_annotations())
                    return
                else:
                    _json(self, {"error": "not found"}, 404)
                    return
                _json(self, value.model_dump(mode="json"))
            except (ReviewError, ValueError, OSError) as error:
                _json(self, {"error": str(error)}, 400)

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


__all__ = [
    "REVIEW_SCHEMA_VERSION",
    "ReviewCase",
    "ReviewDecision",
    "ReviewPacket",
    "ReviewSpan",
    "build_review_fixture",
    "build_review_packet",
    "read_review_packet",
    "serve_review",
    "write_bioc_xml",
]
