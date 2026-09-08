"""Tests for the optional Ab3P adapter; no external executable is required."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any, cast

import pytest

from abrex.config import ComponentSpec
from abrex.domain import Document, TextSpan
from abrex.infrastructure.ab3p import (
    Ab3PCache,
    Ab3PCacheMiss,
    Ab3PExecutionError,
    Ab3PInstallationError,
    Ab3PRawResult,
    cache_key,
    installation_identity,
    run_ab3p,
)
from abrex.resolvers import (
    Ab3PCacheConfig,
    Ab3PInstallationConfig,
    Ab3PMappingError,
    Ab3PParseError,
    Ab3PResolverConfig,
    build_ab3p_input,
    create_resolver_executor,
    parse_ab3p_offset_output,
    parse_ab3p_output,
    reconstruct_offset_predictions,
    reconstruct_predictions,
)
from abrex.resolvers.adapters.ab3p import ParsedAbbreviation
from abrex.resolvers.adapters.ab3p_resolver import Ab3PResolver


def _config(
    path: Path,
    *,
    backend: str = "cache_only",
    label: str | None = None,
    digest: str | None = "a" * 64,
) -> Ab3PResolverConfig:
    return Ab3PResolverConfig(
        backend=backend,
        executable="/opt/ab3p/identify_abbr" if backend != "cache_only" else None,
        installation_label=label,
        cache=Ab3PCacheConfig(path=str(path), read=True, write=True),
        executable_sha256=digest,
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


def test_native_offsets_map_repeated_unicode_and_crlf_lines() -> None:
    first = "Café study of tumor necrosis factor (TNF); tumor necrosis factor (TNF)"
    second = "第二行: interleukin 6 (IL-6) is measured."
    document = Document("native", first + "\r\n" + second)
    first_bytes = first.encode("utf-8")
    second_bytes = second.encode("utf-8")
    records = [
        {
            "schema_version": "ab3p-offsets-v1",
            "line_index": 0,
            "line_start_byte": 0,
            "line_byte_length": len(first_bytes) + 1,
            "short_form": "TNF",
            "long_form": "tumor necrosis factor",
            "precision": 0.95,
            "strategy": "Paren",
            "sf_offset": len("Café study of tumor necrosis factor (".encode()),
            "lf_offset": len("Café study of ".encode()),
        },
        {
            "schema_version": "ab3p-offsets-v1",
            "line_index": 0,
            "line_start_byte": 0,
            "line_byte_length": len(first_bytes) + 1,
            "short_form": "TNF",
            "long_form": "tumor necrosis factor",
            "precision": 0.95,
            "strategy": "Paren",
            "sf_offset": len(
                "Café study of tumor necrosis factor (TNF); "
                "tumor necrosis factor (".encode()
            ),
            "lf_offset": len("Café study of tumor necrosis factor (TNF); ".encode()),
        },
        {
            "schema_version": "ab3p-offsets-v1",
            "line_index": 1,
            "line_start_byte": len(first_bytes) + 2,
            "line_byte_length": len(second_bytes),
            "short_form": "IL-6",
            "long_form": "interleukin 6",
            "precision": 0.8,
            "strategy": "Paren",
            "sf_offset": len("第二行: interleukin 6 (".encode()),
            "lf_offset": len("第二行: ".encode()),
        },
    ]
    parsed = parse_ab3p_offset_output(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    )
    predictions = reconstruct_offset_predictions(document, parsed)
    assert len(predictions) == 3
    assert all(item.long_form is not None for item in predictions)
    assert all(item.short_form is not None for item in predictions)
    assert [
        document.text_for(cast(TextSpan, item.long_form)) for item in predictions
    ] == [
        "tumor necrosis factor",
        "tumor necrosis factor",
        "interleukin 6",
    ]
    assert [
        document.text_for(cast(TextSpan, item.short_form)) for item in predictions
    ] == [
        "TNF",
        "TNF",
        "IL-6",
    ]
    assert predictions[0].long_form != predictions[1].long_form
    assert predictions[2].short_form is not None
    assert predictions[2].short_form.start == document.text.index("IL-6")
    assert predictions[0].long_form is not None
    assert predictions[1].long_form is not None
    assert predictions[0].provenance is not None
    assert (
        "native_ab3p_strategy=Paren" in predictions[0].provenance.transformation_notes
    )


def test_native_offset_mapping_rejects_bad_boundaries_and_surface_text() -> None:
    document = Document("native", "β blocker (BB)")
    line_byte_length = len(document.text.encode("utf-8"))
    base = {
        "schema_version": "ab3p-offsets-v1",
        "line_index": 0,
        "line_start_byte": 0,
        "line_byte_length": line_byte_length,
        "short_form": "BB",
        "long_form": "β blocker",
        "precision": 1.0,
        "strategy": "Paren",
        "sf_offset": len("β blocker (".encode()),
        "lf_offset": 0,
    }
    valid = parse_ab3p_offset_output(json.dumps(base))
    assert valid[0].long_form is not None
    mapped = reconstruct_offset_predictions(document, valid)[0]
    assert document.text_for(cast(TextSpan, mapped.long_form)) == "β blocker"
    boundary = dict(base, lf_offset=1)
    with pytest.raises(Ab3PMappingError, match="UTF-8 boundary"):
        reconstruct_offset_predictions(
            document, parse_ab3p_offset_output(json.dumps(boundary))
        )
    mismatch = dict(base, long_form="wrong form")
    with pytest.raises(Ab3PMappingError, match="does not slice"):
        reconstruct_offset_predictions(
            document, parse_ab3p_offset_output(json.dumps(mismatch))
        )
    with pytest.raises(Ab3PMappingError, match="offsets are missing"):
        reconstruct_offset_predictions(
            document, (ParsedAbbreviation("BB", "β blocker", 1.0),)
        )
    outside = dict(base, line_index=1)
    with pytest.raises(Ab3PMappingError, match="outside"):
        reconstruct_offset_predictions(
            document, parse_ab3p_offset_output(json.dumps(outside))
        )
    with pytest.raises(Ab3PMappingError, match="line origin mismatch"):
        reconstruct_offset_predictions(
            document,
            parse_ab3p_offset_output(json.dumps(dict(base, line_start_byte=1))),
        )
    with pytest.raises(Ab3PMappingError, match="line byte length mismatch"):
        reconstruct_offset_predictions(
            document,
            parse_ab3p_offset_output(
                json.dumps(dict(base, line_byte_length=line_byte_length + 1))
            ),
        )


def test_native_parser_rejects_wrong_schema_and_malformed_records() -> None:
    assert parse_ab3p_offset_output("\n") == ()
    with pytest.raises(TypeError):
        parse_ab3p_offset_output(None)  # type: ignore[arg-type]
    with pytest.raises(Ab3PParseError, match="Unsupported native Ab3P schema"):
        parse_ab3p_offset_output('{"schema_version":"old"}')
    with pytest.raises(Ab3PParseError, match="Malformed native Ab3P JSON"):
        parse_ab3p_offset_output("not-json")
    with pytest.raises(Ab3PParseError, match="must be an object"):
        parse_ab3p_offset_output("[]")
    with pytest.raises(Ab3PParseError, match="Empty native Ab3P form"):
        parse_ab3p_offset_output(
            json.dumps(
                {
                    "schema_version": "ab3p-offsets-v1",
                    "short_form": "",
                    "long_form": "Long",
                    "precision": 1.0,
                    "line_index": 0,
                    "line_start_byte": 0,
                    "line_byte_length": 4,
                    "sf_offset": 0,
                    "lf_offset": 0,
                }
            )
        )
    with pytest.raises(Ab3PParseError, match="precision out of range"):
        parse_ab3p_offset_output(
            json.dumps(
                {
                    "schema_version": "ab3p-offsets-v1",
                    "short_form": "S",
                    "long_form": "Long",
                    "precision": 2.0,
                    "line_index": 0,
                    "line_start_byte": 0,
                    "line_byte_length": 4,
                    "sf_offset": 0,
                    "lf_offset": 0,
                }
            )
        )
    with pytest.raises(Ab3PParseError, match="line_index"):
        parse_ab3p_offset_output(
            json.dumps(
                {
                    "schema_version": "ab3p-offsets-v1",
                    "short_form": "S",
                    "long_form": "Long",
                    "precision": 1.0,
                    "line_index": -1,
                    "line_start_byte": 0,
                    "line_byte_length": 4,
                    "sf_offset": 0,
                    "lf_offset": 0,
                }
            )
        )
    with pytest.raises(Ab3PParseError, match="short_form must be a string"):
        parse_ab3p_offset_output(
            json.dumps(
                {
                    "schema_version": "ab3p-offsets-v1",
                    "short_form": 1,
                    "long_form": "Long",
                    "precision": 1.0,
                    "line_index": 0,
                    "line_start_byte": 0,
                    "line_byte_length": 4,
                    "sf_offset": 0,
                    "lf_offset": 0,
                }
            )
        )
    with pytest.raises(Ab3PParseError, match="strategy must be a string or null"):
        parse_ab3p_offset_output(
            json.dumps(
                {
                    "schema_version": "ab3p-offsets-v1",
                    "short_form": "S",
                    "long_form": "Long",
                    "precision": 1.0,
                    "line_index": 0,
                    "line_start_byte": 0,
                    "line_byte_length": 4,
                    "sf_offset": 0,
                    "lf_offset": 0,
                    "strategy": 1,
                }
            )
        )


def test_cache_round_trip_is_portable_and_identity_is_explicit(tmp_path: Path) -> None:
    document = Document("d1", "Tumor necrosis factor (TNF)")
    live_config = _config(tmp_path, backend="subprocess", label="linux-ab3p")
    offline_config = _config(tmp_path, label="linux-ab3p")
    assert cache_key(document, live_config) == cache_key(document, offline_config)
    offset_config = live_config.model_copy(update={"output_format": "offset_jsonl"})
    assert cache_key(document, offset_config) != cache_key(document, live_config)
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
        cache.read(document, _config(tmp_path, label="linux-ab3p", digest="b" * 64))
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


def test_cache_requires_an_explicit_installation_identity(tmp_path: Path) -> None:
    invalid = Ab3PResolverConfig.model_construct(
        backend="cache_only",
        executable=None,
        cache=Ab3PCacheConfig(path=str(tmp_path)),
        installation=None,
        installation_label=None,
        executable_sha256=None,
    )
    with pytest.raises(Ab3PInstallationError, match="requires the T018"):
        installation_identity(invalid, require_runtime=False)
    with pytest.raises(ValueError, match="installation_label alone"):
        _config(tmp_path, digest=None)


def test_invalid_installation_manifest_is_explicit(tmp_path: Path) -> None:
    root, manifest = _installation(tmp_path)
    config = Ab3PResolverConfig(
        backend="cache_only",
        installation=Ab3PInstallationConfig(manifest=str(manifest)),
        cache=Ab3PCacheConfig(path=str(tmp_path / "cache")),
    )
    manifest.write_text("[]", encoding="utf-8")
    with pytest.raises(Ab3PInstallationError, match="Incompatible"):
        installation_identity(config, require_runtime=False)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "ab3p-installation-v1",
                "artifacts": [
                    {
                        "path": "../identify_abbr",
                        "role": "executable",
                        "sha256": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(Ab3PInstallationError, match="escapes"):
        installation_identity(config, require_runtime=False)
    manifest.unlink()
    with pytest.raises(Ab3PInstallationError, match="Unable to read"):
        installation_identity(config, require_runtime=False)
    manifest.write_text(
        json.dumps({"schema_version": "ab3p-installation-v1", "artifacts": [1]}),
        encoding="utf-8",
    )
    with pytest.raises(Ab3PInstallationError, match="must be an object"):
        installation_identity(config, require_runtime=False)
    manifest.write_text(
        json.dumps({"schema_version": "ab3p-installation-v1", "artifacts": [{}]}),
        encoding="utf-8",
    )
    with pytest.raises(Ab3PInstallationError, match="incomplete"):
        installation_identity(config, require_runtime=False)
    assert root.is_dir()


def test_configured_executable_digest_is_part_of_cache_compatibility(
    tmp_path: Path,
) -> None:
    document = Document("d1", "text")
    digest = "a" * 64
    config = Ab3PResolverConfig(
        backend="cache_only",
        executable_sha256=digest,
        cache=Ab3PCacheConfig(path=str(tmp_path), read=True, write=True),
    )
    cache = Ab3PCache(tmp_path)
    cache.write(
        document, config, Ab3PRawResult("text\n", "", 0, executable_sha256=digest)
    )
    assert cache.read(document, config).executable_sha256 == digest
    mismatched = config.model_copy(update={"executable_sha256": "b" * 64})
    with pytest.raises(Ab3PCacheMiss):
        cache.read(document, mismatched)


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
                "executable_sha256": "a" * 64,
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
        Ab3PResolver(
            **{
                "backend": "cache_only",
                "cache": {"path": "x"},
                "executable_sha256": "a" * 64,
            }
        ).identity
        == "ab3p"
    )


def _installation(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "installation"
    (root / "WordData").mkdir(parents=True)
    executable = root / "identify_abbr"
    resource = root / "WordData" / "Ab3P_prec.dat"
    executable.write_bytes(b"executable-a")
    resource.write_bytes(b"resource-a")
    (root / "path_Ab3P").write_text("WordData\n", encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = tmp_path / "installation-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "ab3p-installation-v1",
                "artifacts": [
                    {
                        "path": "identify_abbr",
                        "role": "executable",
                        "sha256": digest(executable),
                    },
                    {
                        "path": "WordData/Ab3P_prec.dat",
                        "role": "semantic-resource",
                        "sha256": digest(resource),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return root, manifest


def test_manifest_identity_rejects_changed_runtime_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest = _installation(tmp_path)
    live = Ab3PResolverConfig(
        backend="subprocess",
        installation=Ab3PInstallationConfig(manifest=str(manifest), root=str(root)),
        cache=Ab3PCacheConfig(path=str(tmp_path / "cache"), read=True, write=True),
    )
    offline = Ab3PResolverConfig(
        backend="cache_only",
        installation=Ab3PInstallationConfig(manifest=str(manifest)),
        cache=Ab3PCacheConfig(path=str(tmp_path / "cache"), read=True, write=False),
    )
    assert installation_identity(live, require_runtime=True) == installation_identity(
        offline, require_runtime=False
    )
    document = Document("d1", "Tumor necrosis factor (TNF)")
    cache = Ab3PCache(tmp_path / "cache")
    identity = installation_identity(live, require_runtime=True)
    cache.write(
        document,
        live,
        Ab3PRawResult(
            "echo\n TNF|Tumor necrosis factor|0.9\n", "", 0, cache_identity=identity
        ),
    )
    assert cache.read(document, offline).cache_identity == identity
    calls: list[dict[str, object]] = []

    class Completed:
        stdout = "text\n"
        stderr = ""
        returncode = 0

    def run(*args: object, **kwargs: object) -> Completed:
        calls.append(kwargs)
        return Completed()

    monkeypatch.setattr("abrex.infrastructure.ab3p.subprocess.run", run)
    live_result = run_ab3p(document, live)
    assert live_result.cache_identity == identity
    assert calls[0]["cwd"] == root
    (root / "WordData" / "Ab3P_prec.dat").write_bytes(b"resource-b")
    with pytest.raises(Ab3PInstallationError, match="fingerprint mismatch"):
        installation_identity(live, require_runtime=True)
    with pytest.raises(Ab3PCacheMiss, match="identity is unavailable"):
        cache.read(document, live)


def test_relative_installation_root_is_resolved_before_subprocess_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest = _installation(tmp_path)
    monkeypatch.chdir(tmp_path)
    live = Ab3PResolverConfig(
        backend="subprocess",
        installation=Ab3PInstallationConfig(
            manifest=manifest.name,
            root=root.name,
        ),
    )
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class Completed:
        stdout = "text\n"
        stderr = ""
        returncode = 0

    def run(*args: object, **kwargs: object) -> Completed:
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr("abrex.infrastructure.ab3p.subprocess.run", run)
    run_ab3p(Document("d", "text"), live)
    argv = calls[0][0][0]
    assert isinstance(argv, list)
    assert argv[0] == str(root / "identify_abbr")
    assert calls[0][1]["cwd"] == root.resolve()


def test_subprocess_success_failure_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = Document("d", "text")
    config = Ab3PResolverConfig(
        backend="subprocess", executable="ab3p", executable_sha256="a" * 64
    )

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
    with pytest.raises(Ab3PExecutionError, match="verified installation"):
        run_ab3p(
            document,
            Ab3PResolverConfig(
                backend="cache_only",
                cache=Ab3PCacheConfig(path="x"),
                executable_sha256="a" * 64,
            ),
        )


def test_resolver_cache_then_subprocess_miss_is_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = Document("d", "text")
    config = {
        "backend": "cache_then_subprocess",
        "executable": "ab3p",
        "installation_label": "test-ab3p",
        "executable_sha256": "a" * 64,
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
        executable_sha256="a" * 64,
    )
    with pytest.raises(Exception, match="cache"):
        tuple(no_read.resolve(document))
