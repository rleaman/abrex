"""Public T052 reviewer facade and small local HTTP application."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

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
    validate_annotation_state,
)
from abrex.literature.review_packet import (
    build_review_fixture,
    build_review_packet,
    read_review_packet,
)
from abrex.literature.reviewer_ui import REVIEWER_HTML

# Kept as a deliberately small compatibility surface for the package facade.
REVIEW_SCHEMA_VERSION = "t052-review-packet-v2"
ReviewDecision = object


class _ReviewerState:
    def __init__(self, packet_path: Path) -> None:
        self.packet_path = packet_path
        self.packet = read_review_packet(packet_path)
        # Keep annotation backups content-addressed to the packet filename so
        # a corrected packet cannot accidentally load the legacy packet's
        # state.  A packet/content mismatch is still rejected by the state
        # validator when a sidecar is deliberately copied into this location.
        self.state_path = packet_path.with_name(f"{packet_path.stem}.annotations.json")
        self.lock = threading.RLock()
        self.state = read_annotation_state(self.packet, self.state_path)

    def save_submission(self, payload: bytes) -> AnnotationState:
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


def _json(handler: BaseHTTPRequestHandler, value: object, status: int = 200) -> None:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def serve_review(
    packet_path: Path, *, host: str = "127.0.0.1", port: int = 8765
) -> None:
    """Serve a packet until interrupted. State is persisted beside the packet."""
    app = _ReviewerState(Path(packet_path))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/":
                body = REVIEWER_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif route == "/api/packet":
                _json(self, app.packet.model_dump(mode="json"))
            elif route == "/api/annotations":
                _json(self, app.state.model_dump(mode="json"))
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
                elif route == "/api/import/bioc":
                    with app.lock:
                        value = import_bioc_xml(app.packet, payload, app.state)
                        write_annotation_state(value, app.state_path)
                        app.state = value
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
