"""Runnable configuration contracts for locally available historical corpora."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abrex.cli import main
from abrex.config import ConfigError, load_resolved_config
from abrex.corpora import (
    CorpusOutputConfig,
    corpus_config_from_resolved,
    create_corpus_pipeline,
    load_corpus_build_groups,
    read_canonical_jsonl,
    read_dataset_manifest,
)

CORPUS_CONFIG_DIR = Path("configs/corpora")


def test_every_committed_historical_config_loads_and_resolves() -> None:
    paths = tuple(sorted(CORPUS_CONFIG_DIR.glob("*.yaml")))
    assert paths
    for path in paths:
        config = load_resolved_config((path,))
        corpus = corpus_config_from_resolved(config)
        assert corpus.adapter.type in {
            "ab3p_corpus",
            "bioadi",
            "medstract",
            "schwartz_hearst",
            "sdu_aaai21_ai",
            "sdu_aaai21_ad",
            "sdu_aaai22_ae",
        }
        assert corpus.source.location is not None
        assert not corpus.source.location.is_absolute()
        # Raw historical sources are user-managed and intentionally absent
        # from a fresh checkout.  Build tests use committed synthetic fixtures.
        assert corpus.source.location.parts[:2] == ("data", "raw")
        assert corpus.normalizers
        assert corpus.strict is False
        assert corpus.output is not None
        assert corpus.output.directory.parts[:2] == ("data", "processed")
        pipeline = create_corpus_pipeline(corpus)
        assert pipeline.adapter.identity == corpus.adapter.type


def test_historical_group_is_configuration_driven() -> None:
    groups = load_corpus_build_groups(Path("configs/corpus-groups.yaml"))
    assert groups.paths_for("historical") == (
        Path("configs/corpora/ab3p.yaml"),
        Path("configs/corpora/bioadi.yaml"),
        Path("configs/corpora/medstract.yaml"),
        Path("configs/corpora/schwartz_hearst.yaml"),
        Path("configs/corpora/sdu_aaai21_ai.yaml"),
        Path("configs/corpora/sdu_aaai21_ad.yaml"),
        Path("configs/corpora/sdu_aaai22_ae.yaml"),
    )
    with pytest.raises(ConfigError, match="available groups"):
        groups.paths_for("missing")


def test_fixture_build_uses_declared_output_and_t004_artifacts(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "fixture.yaml"
    output_directory = tmp_path / "processed" / "fixture"
    config_path.write_text(
        f"""
corpus:
  adapter:
    type: fixture
    params: {{}}
  source:
    identifier: embedded-fixture
  normalizers:
    - type: identity
      params: {{}}
  strict: false
  output:
    directory: {output_directory.as_posix()}
    jsonl: canonical.jsonl
    manifest: manifest.json
""",
        encoding="utf-8",
    )

    assert main(["corpus", "build", "--config", str(config_path)]) == 0

    jsonl = output_directory / "canonical.jsonl"
    manifest_path = output_directory / "manifest.json"
    records = read_canonical_jsonl(jsonl)
    manifest = read_dataset_manifest(manifest_path)
    assert records
    assert manifest.record_count == len(records)
    assert manifest.adapter_identity == "fixture"
    assert manifest.normalizer_identities == ("identity",)
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["schema_version"] == (
        "canonical-v1"
    )


def test_build_all_composes_single_build_for_a_test_group(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus_config = tmp_path / "fixture.yaml"
    output_directory = tmp_path / "processed"
    corpus_config.write_text(
        f"""
corpus:
  adapter: {{type: fixture, params: {{}}}}
  source: {{identifier: grouped-fixture}}
  normalizers: [{{type: identity, params: {{}}}}]
  strict: false
  output: {{directory: {output_directory.as_posix()}}}
""",
        encoding="utf-8",
    )
    groups_config = tmp_path / "groups.yaml"
    groups_config.write_text(
        f"groups:\n  test:\n    configs:\n      - {corpus_config.as_posix()}\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "corpus",
                "build-all",
                "--group",
                "test",
                "--groups-config",
                str(groups_config),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert len(result) == 1
    assert result[0]["adapter"]["identity"] == "fixture"
    assert (output_directory / "canonical.jsonl").is_file()
    assert (output_directory / "manifest.json").is_file()


def test_corpus_cli_reports_missing_config_output_and_group(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["corpus", "build"]) == 2
    assert "requires --config" in capsys.readouterr().err

    no_output = tmp_path / "no-output.yaml"
    no_output.write_text(
        "corpus:\n  adapter: {type: fixture, params: {}}\n", encoding="utf-8"
    )
    assert main(["corpus", "build", "--config", str(no_output)]) == 2
    assert "must declare output" in capsys.readouterr().err

    assert (
        main(
            [
                "corpus",
                "build-all",
                "--group",
                "missing",
                "--groups-config",
                "configs/corpus-groups.yaml",
            ]
        )
        == 2
    )
    assert "available groups" in capsys.readouterr().err


def test_output_config_rejects_unsafe_artifact_names() -> None:
    with pytest.raises(ValueError, match="relative paths"):
        CorpusOutputConfig(directory=Path("data/processed"), jsonl="../escape")

    with pytest.raises(ValueError, match="relative paths"):
        CorpusOutputConfig(directory=Path("data/processed"), manifest="C:/escape")


def test_group_loader_reports_invalid_configuration(tmp_path: Path) -> None:
    path = tmp_path / "invalid-groups.yaml"
    path.write_text("groups:\n  historical:\n    configs: []\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid corpus group"):
        load_corpus_build_groups(path)
