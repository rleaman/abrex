"""Tests for the optional BioADI adapter and bounded subprocess boundary."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from abrex.domain import Document
from abrex.infrastructure.bioadi import (
    BioADIExecutionError,
    BioADIRawResult,
    bioadi_identity,
    run_bioadi,
)
from abrex.resolvers import (
    BioADIMappingError,
    BioADIPair,
    BioADIParseError,
    BioADIResolver,
    BioADIResolverConfig,
    parse_bioadi_output,
    reconstruct_bioadi_predictions,
)


def _config(jar: Path, *, policy: str = "ordered_occurrence") -> BioADIResolverConfig:
    return BioADIResolverConfig(
        jar_path=jar,
        jar_sha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
        mapping_policy=policy,  # type: ignore[arg-type]
    )


def test_parser_ignores_echo_and_preserves_scores() -> None:
    output = (
        "doc-1\n"
        "Tumor necrosis factor (TNF) is studied.\n"
        "  TNF|Tumor necrosis factor|0.95\n"
    )
    assert parse_bioadi_output(output) == (
        BioADIPair("TNF", "Tumor necrosis factor", 0.95),
    )
    assert parse_bioadi_output("no pairs here\n") == ()
    with pytest.raises(BioADIParseError, match="Malformed"):
        parse_bioadi_output("  TNF|factor\n")
    with pytest.raises(BioADIParseError, match="Invalid"):
        parse_bioadi_output("  TNF|factor|bad\n")
    with pytest.raises(BioADIParseError, match="out of range"):
        parse_bioadi_output("  TNF|factor|1.1\n")
    with pytest.raises(TypeError):
        parse_bioadi_output(None)  # type: ignore[arg-type]


def test_ordered_occurrence_mapping_handles_repeated_pairs() -> None:
    document = Document(
        "d1",
        "tumor necrosis factor (TNF); tumor necrosis factor (TNF)",
    )
    pair = BioADIPair("TNF", "tumor necrosis factor", 0.8)
    predictions = reconstruct_bioadi_predictions(document, (pair, pair))
    assert len(predictions) == 2
    assert predictions[0].short_form != predictions[1].short_form
    assert predictions[0].long_form != predictions[1].long_form
    assert predictions[0].prediction is not None
    assert predictions[0].prediction.score == 0.8
    assert predictions[0].provenance is not None
    assert (
        "source_offsets=not_reported"
        in predictions[0].provenance.transformation_notes[1]
    )


def test_mapping_policies_reject_ambiguous_or_unsafe_rows() -> None:
    document = Document(
        "d1", "Tumor necrosis factor (TNF); Tumor necrosis factor (TNF)"
    )
    pair = BioADIPair("TNF", "Tumor necrosis factor", 1.0)
    with pytest.raises(BioADIMappingError, match="not unique"):
        reconstruct_bioadi_predictions(
            document, (pair,), mapping_policy="strict_unique"
        )
    with pytest.raises(BioADIMappingError, match="does not reconcile"):
        reconstruct_bioadi_predictions(document, (pair,))
    with pytest.raises(BioADIMappingError, match="long-before-short"):
        reconstruct_bioadi_predictions(
            Document("d2", "TNF means Tumor necrosis factor"),
            (pair,),
        )
    with pytest.raises(BioADIMappingError, match="does not reconcile"):
        reconstruct_bioadi_predictions(Document("d3", "nothing"), (pair,))
    with pytest.raises(ValueError, match="Unsupported"):
        reconstruct_bioadi_predictions(document, (pair,), mapping_policy="other")  # type: ignore[arg-type]


def test_identity_verifies_the_pinned_jar_and_resolver_cache_identity(
    tmp_path: Path,
) -> None:
    jar = tmp_path / "bioadi.jar"
    jar.write_bytes(b"test jar")
    config = _config(jar)
    identity = bioadi_identity(config)
    assert identity["jar_sha256"] == hashlib.sha256(b"test jar").hexdigest()
    assert identity["entry_point"] == "aiiaadi.util.Executor"
    assert BioADIResolver(**config.model_dump()).cache_identity == identity
    with pytest.raises(BioADIExecutionError, match="digest mismatch"):
        bioadi_identity(config.model_copy(update={"jar_sha256": "0" * 64}))
    with pytest.raises(BioADIExecutionError, match="does not exist"):
        bioadi_identity(
            config.model_copy(update={"jar_path": tmp_path / "missing.jar"})
        )


def test_run_bioadi_builds_bounded_wsl_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bioadi.jar"
    jar.write_bytes(b"test jar")
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["timeout"] == 35
        return subprocess.CompletedProcess(
            command, 0, "  TNF|Tumor necrosis factor|0.9\n", ""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_bioadi(
        Document("doc-1", "Tumor necrosis factor (TNF)"),
        _config(jar),
    )
    assert result.exit_status == 0
    assert "aiiaadi.util.Executor" in calls[0][-1]
    assert "/mnt/" in calls[0][-1]


def test_run_bioadi_reports_missing_jar_and_subprocess_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.jar"
    config = BioADIResolverConfig(jar_path=missing, jar_sha256="0" * 64)
    with pytest.raises(BioADIExecutionError, match="does not exist"):
        run_bioadi(Document("d", "text"), config)

    jar = tmp_path / "bioadi.jar"
    jar.write_bytes(b"jar")

    def timeout_run(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("wsl.exe", 35)

    monkeypatch.setattr(subprocess, "run", timeout_run)
    with pytest.raises(BioADIExecutionError, match="Unable to execute"):
        run_bioadi(Document("d", "text"), _config(jar))


def test_resolver_handles_runtime_result_and_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bioadi.jar"
    jar.write_bytes(b"jar")
    document = Document("d", "Tumor necrosis factor (TNF)")
    resolver = BioADIResolver(**_config(jar).model_dump())
    monkeypatch.setattr(
        "abrex.infrastructure.bioadi.run_bioadi",
        lambda _document, _config: BioADIRawResult(
            "  TNF|Tumor necrosis factor|0.9\n", "", 0
        ),
    )
    predictions = tuple(resolver.resolve(document))
    assert len(predictions) == 1
    monkeypatch.setattr(
        "abrex.infrastructure.bioadi.run_bioadi",
        lambda _document, _config: BioADIRawResult("", "", 124, True),
    )
    with pytest.raises(RuntimeError, match="timed out"):
        resolver.resolve(document)
    monkeypatch.setattr(
        "abrex.infrastructure.bioadi.run_bioadi",
        lambda _document, _config: BioADIRawResult("", "bad", 2),
    )
    with pytest.raises(RuntimeError, match="status 2"):
        resolver.resolve(document)
