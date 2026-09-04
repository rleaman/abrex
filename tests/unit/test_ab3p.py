"""Tests for the optional Ab3P adapter; no external executable is required."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any

import pytest

from abrex.config import ComponentSpec
from abrex.domain import Document
from abrex.infrastructure.ab3p import (
    Ab3PCache,
    Ab3PCacheMiss,
    Ab3PExecutionError,
    Ab3PRawResult,
    cache_key,
    run_ab3p,
)
from abrex.resolvers import (
    Ab3PCacheConfig,
    Ab3PMappingError,
    Ab3PParseError,
    Ab3PResolverConfig,
    build_ab3p_input,
    create_resolver_executor,
    parse_ab3p_output,
    reconstruct_predictions,
)
from abrex.resolvers.adapters.ab3p_resolver import Ab3PResolver


def _config(
    path: Path, *, backend: str = "cache_only", label: str | None = None
) -> Ab3PResolverConfig:
    return Ab3PResolverConfig(
        backend=backend,
        executable="/opt/ab3p/identify_abbr" if backend != "cache_only" else None,
        installation_label=label,
        cache=Ab3PCacheConfig(path=str(path), read=True, write=True),
    )


def test_input_parser_mapping_and_zero_output() -> None:
    document = Document("d1", "Tumor necrosis factor (TNF) is studied.")
    assert build_ab3p_input(document) == document.text
    parsed = parse_ab3p_output(
        "Tumor necrosis factor (TNF) is studied.\n  TNF|Tumor necrosis factor|0.95\n"
    )
    assert parsed[0].precision == 0.95
    prediction = reconstruct_predictions(document, parsed)[0]
    assert prediction.short_form is not None
    assert prediction.long_form is not None
    assert document.text_for(prediction.short_form) == "TNF"
    assert document.text_for(prediction.long_form) == "Tumor necrosis factor"
    assert parse_ab3p_output("No definitions here\n") == ()
    assert parse_ab3p_output("No definitions here\n \n") == ()
    with pytest.raises(TypeError):
        build_ab3p_input("not a document")  # type: ignore[arg-type]
    assert parse_ab3p_output("echo\n\n") == ()
    with pytest.raises(Ab3PParseError):
        parse_ab3p_output("echo\n TNF||0.5\n")
    with pytest.raises(TypeError):
        parse_ab3p_output(None)  # type: ignore[arg-type]


def test_parser_rejects_malformed_output_and_mapping_ambiguity() -> None:
    with pytest.raises(Ab3PParseError):
        parse_ab3p_output("echo\n  TNF|factor|not-a-number\n")
    with pytest.raises(Ab3PParseError):
        parse_ab3p_output("echo\n  TNF|factor\n")
    with pytest.raises(Ab3PParseError):
        parse_ab3p_output("echo\n  TNF|factor|2\n")
    pair = parse_ab3p_output("echo\n TNF|Tumor necrosis factor|1\n")[0]
    with pytest.raises(Ab3PMappingError, match="ambiguous"):
        reconstruct_predictions(
            Document("d", "Tumor necrosis factor (TNF); Tumor necrosis factor (TNF)"),
            (pair,),
        )
    with pytest.raises(Ab3PMappingError, match="not found"):
        reconstruct_predictions(Document("d", "nothing"), (pair,))


def test_cache_round_trip_is_portable_and_identity_is_explicit(tmp_path: Path) -> None:
    document = Document("d1", "Tumor necrosis factor (TNF)")
    live_config = _config(tmp_path, backend="subprocess", label="linux-ab3p")
    offline_config = _config(tmp_path, label="linux-ab3p")
    assert cache_key(document, live_config) == cache_key(document, offline_config)
    result = Ab3PRawResult("echo\n TNF|Tumor necrosis factor|0.9\n", "", 0)
    cache = Ab3PCache(tmp_path)
    path = cache.write(document, live_config, result)
    replayed = cache.read(document, offline_config)
    assert replayed.stdout == result.stdout
    assert path.name == f"{cache_key(document, live_config)}.json"
    valid = json.loads(path.read_text(encoding="utf-8"))
    with pytest.raises(Ab3PCacheMiss):
        cache.read(Document("d1", "changed"), offline_config)
    with pytest.raises(Ab3PCacheMiss):
        cache.read(document, _config(tmp_path, label="different"))
    broken = tmp_path / f"{cache_key(document, offline_config)}.json"
    broken.write_text("[]", encoding="utf-8")
    with pytest.raises(Ab3PCacheMiss):
        cache.read(document, offline_config)
    valid["provenance"] = None
    broken.write_text(json.dumps(valid), encoding="utf-8")
    with pytest.raises(Ab3PCacheMiss):
        cache.read(document, offline_config)
    broken.write_text(
        '{"schema_version":"ab3p-cache-v1","cache_key":"x"}', encoding="utf-8"
    )
    with pytest.raises(Ab3PCacheMiss):
        cache.read(document, offline_config)


def test_cache_only_resolver_replays_same_parser_path_and_misses(
    tmp_path: Path,
) -> None:
    document = Document("d1", "Tumor necrosis factor (TNF)")
    live = _config(tmp_path, backend="subprocess", label="linux-ab3p")
    Ab3PCache(tmp_path).write(
        document, live, Ab3PRawResult("echo\n TNF|Tumor necrosis factor|0.9\n", "", 0)
    )
    executor = create_resolver_executor(
        ComponentSpec(
            type="ab3p",
            params={
                "backend": "cache_only",
                "cache": {"path": str(tmp_path), "read": True, "write": False},
                "installation_label": "linux-ab3p",
            },
        )
    )
    record = executor.resolve_document(document)
    assert len(record.predictions) == 1
    with pytest.raises(Exception, match="cache"):
        create_resolver_executor(
            ComponentSpec(
                type="ab3p",
                params={
                    "backend": "cache_only",
                    "cache": {"path": str(tmp_path), "read": True, "write": False},
                },
            )
        ).resolve_document(Document("other", "text"))


def test_config_validation_and_resolver_registry() -> None:
    with pytest.raises(ValueError, match="Unsupported Ab3P backend"):
        Ab3PResolverConfig(backend="unknown")
    with pytest.raises(ValueError, match="requires executable"):
        Ab3PResolverConfig(backend="subprocess")
    with pytest.raises(ValueError, match="requires cache"):
        Ab3PResolverConfig(backend="cache_only")
    assert (
        Ab3PResolverConfig(backend="subprocess", executable="ab3p").backend
        == "subprocess"
    )
    assert (
        Ab3PResolver(**{"backend": "cache_only", "cache": {"path": "x"}}).identity
        == "ab3p"
    )


def test_subprocess_success_failure_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = Document("d", "text")
    config = Ab3PResolverConfig(backend="subprocess", executable="ab3p")

    class Completed:
        stdout = "text\n"
        stderr = ""
        returncode = 0

    calls: list[tuple[Any, ...]] = []

    def success(*args: Any, **kwargs: Any) -> Completed:
        calls.append(args)
        return Completed()

    monkeypatch.setattr("abrex.infrastructure.ab3p.subprocess.run", success)
    assert isinstance(run_ab3p(document, config), Ab3PRawResult)
    assert calls

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise TimeoutExpired(args[0], 1)

    monkeypatch.setattr("abrex.infrastructure.ab3p.subprocess.run", fail)
    with pytest.raises(Ab3PExecutionError, match="timed out"):
        run_ab3p(document, config)

    monkeypatch.setattr(
        "abrex.infrastructure.ab3p.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("unavailable")),
    )
    with pytest.raises(Ab3PExecutionError, match="Unable to execute"):
        run_ab3p(document, config)

    monkeypatch.setattr(
        Path,
        "write_bytes",
        lambda self, value: (_ for _ in ()).throw(OSError("disk")),
    )
    with pytest.raises(Ab3PExecutionError, match="prepare"):
        run_ab3p(document, config)

    monkeypatch.undo()
    monkeypatch.setattr(
        "abrex.infrastructure.ab3p.subprocess.run", lambda *args, **kwargs: Completed()
    )
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"binary")
    assert run_ab3p(document, config).executable_sha256 is not None

    class Failed(Completed):
        returncode = 3
        stderr = "bad"

    monkeypatch.setattr(
        "abrex.infrastructure.ab3p.subprocess.run", lambda *args, **kwargs: Failed()
    )
    with pytest.raises(Ab3PExecutionError, match="status 3"):
        run_ab3p(document, config)
    with pytest.raises(Ab3PExecutionError, match="requires executable"):
        run_ab3p(
            document,
            Ab3PResolverConfig(backend="cache_only", cache=Ab3PCacheConfig(path="x")),
        )


def test_resolver_cache_then_subprocess_miss_is_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = Document("d", "text")
    config = {
        "backend": "cache_then_subprocess",
        "executable": "ab3p",
        "cache": {"path": str(tmp_path), "read": True, "write": False},
    }
    monkeypatch.setattr(
        "abrex.infrastructure.ab3p.run_ab3p",
        lambda document, config: Ab3PRawResult("text\n", "", 0),
    )
    # The resolver imports infrastructure lazily; exercise its public path.
    resolver = Ab3PResolver(**config)
    assert tuple(resolver.resolve(document)) == ()
    write_config = {
        **config,
        "cache": {"path": str(tmp_path), "read": True, "write": True},
    }
    assert tuple(Ab3PResolver(**write_config).resolve(document)) == ()
    no_read = Ab3PResolver(
        backend="cache_only",
        cache={"path": str(tmp_path), "read": False, "write": False},
    )
    with pytest.raises(Exception, match="cache"):
        tuple(no_read.resolve(document))
