"""Focused tests for application logging behavior."""

import logging
from contextlib import suppress
from io import StringIO
from pathlib import Path

import pytest

from abrex.cli import main
from abrex.domain import Document
from abrex.logging import configure_logging
from abrex.resolvers.adapters.ab3p_resolver import Ab3PResolver


def test_configure_logging_is_idempotent_and_uses_stderr() -> None:
    configure_logging(logging.INFO)
    configure_logging(logging.DEBUG)
    root = logging.getLogger()
    handlers = [
        handler
        for handler in root.handlers
        if isinstance(handler, logging.StreamHandler)
        and getattr(handler, "_abrex_handler", False)
    ]
    assert len(handlers) == 1
    assert handlers[0].stream is not None


def test_persistent_handler_follows_replaced_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = StringIO()
    monkeypatch.setattr("sys.stderr", first)
    configure_logging(logging.INFO)
    first.close()
    second = StringIO()
    monkeypatch.setattr("sys.stderr", second)
    logging.getLogger("lifecycle-test").warning("still writable")
    assert "still writable" in second.getvalue()


def test_debug_cli_emits_diagnostics_without_polluting_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("project:\n  name: logging-test\n", encoding="utf-8")

    with caplog.at_level(logging.DEBUG):
        assert (
            main(["--debug", "config", "resolve", str(config), "--format", "json"]) == 0
        )

    captured = capsys.readouterr()
    assert '"name": "logging-test"' in captured.out
    assert "Reading configuration layer" in caplog.text


def test_quiet_cli_suppresses_info_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("project:\n  name: logging-test\n", encoding="utf-8")

    with caplog.at_level(logging.DEBUG):
        assert main(["--quiet", "config", "resolve", str(config)]) == 0

    assert not any(record.levelno == logging.INFO for record in caplog.records)


def test_ab3p_cache_miss_is_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    resolver = Ab3PResolver(
        **{
            "backend": "cache_only",
            "cache": {"path": "not-a-cache", "read": True, "write": False},
            "executable_sha256": "a" * 64,
        }
    )

    with caplog.at_level(logging.WARNING), suppress(LookupError):
        tuple(resolver.resolve(Document("missing", "text")))

    assert any(
        record.levelno == logging.WARNING and "cache miss" in record.message
        for record in caplog.records
    )
