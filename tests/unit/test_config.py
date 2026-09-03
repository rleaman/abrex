"""Configuration loader, merge, serialization, and CLI tests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from abrex.cli import main
from abrex.config import (
    ComponentSpec,
    ConfigError,
    ResolvedConfig,
    dump_resolved_config,
    load_config_layer,
    load_resolved_config,
    merge_config_layers,
    serialize_resolved_config,
)


def write_yaml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_merge_layers_is_recursive_and_later_values_win() -> None:
    first = {"nested": {"keep": 1, "replace": 1}, "list": [1], "scalar": "a"}
    second = {"nested": {"replace": 2}, "list": [2], "scalar": "b"}

    assert merge_config_layers((first, second)) == {
        "nested": {"keep": 1, "replace": 2},
        "list": [2],
        "scalar": "b",
    }
    assert first["nested"] == {"keep": 1, "replace": 1}
    with pytest.raises(ConfigError, match="layer"):
        merge_config_layers(([],))  # type: ignore[arg-type]


def test_load_and_resolve_yaml_with_both_explicit_env_forms(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path / "base.yaml",
        """
project:
  name: demo
  seed: 7
resolver:
  type: toy
  params:
    executable: ${TOY_BIN}
    label: !env LABEL
literal: '$NOT_INTERPOLATED'
items:
  - ${TOY_BIN}
""",
    )
    override = write_yaml(
        tmp_path / "override.yaml",
        """
project:
  seed: 9
items:
  - overridden
""",
    )

    config = load_resolved_config(
        (path, override), environment={"TOY_BIN": "/bin/toy", "LABEL": "test"}
    )
    assert config.project is not None
    assert config.project.name == "demo"
    assert config.project.seed == 9
    assert config.component("resolver").params == {
        "executable": "/bin/toy",
        "label": "test",
    }
    assert config.model_extra is not None
    assert config.model_extra["literal"] == "$NOT_INTERPOLATED"
    assert config.model_extra["items"] == ["overridden"]


def test_empty_environment_is_honored_and_missing_variables_are_reported(
    tmp_path: Path,
) -> None:
    path = write_yaml(tmp_path / "env.yaml", "value: ${MISSING}\n")
    with pytest.raises(ConfigError, match="MISSING.*value"):
        load_resolved_config((path,), environment={})

    tagged = write_yaml(tmp_path / "tagged.yaml", "value: !env BAD-NAME\n")
    with pytest.raises(ConfigError, match="Invalid !env"):
        load_config_layer(tagged)
    missing_tagged = write_yaml(
        tmp_path / "missing-tagged.yaml", "value: !env MISSING\n"
    )
    with pytest.raises(ConfigError, match="MISSING.*value"):
        load_resolved_config((missing_tagged,), environment={})


def test_loading_reports_file_yaml_and_root_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Unable to read"):
        load_config_layer(tmp_path / "missing.yaml")
    malformed = write_yaml(tmp_path / "bad.yaml", "value: [unterminated\n")
    with pytest.raises(ConfigError, match="Malformed YAML.*line"):
        load_config_layer(malformed)
    scalar = write_yaml(tmp_path / "scalar.yaml", "just a scalar\n")
    with pytest.raises(ConfigError, match="root.*mapping"):
        load_config_layer(scalar)
    empty = write_yaml(tmp_path / "empty.yaml", "")
    assert load_config_layer(empty) == {}
    with pytest.raises(ConfigError, match="At least one"):
        load_resolved_config(())


def test_validation_and_component_access_errors(tmp_path: Path) -> None:
    config = ResolvedConfig.model_validate({"resolver": {"type": "toy"}})
    assert config.component("resolver") == ComponentSpec(type="toy")
    with pytest.raises(ValidationError):
        config.component("missing")
    invalid = write_yaml(tmp_path / "invalid.yaml", "project:\n  seed: not-an-int\n")
    with pytest.raises(ConfigError, match="Invalid resolved"):
        load_resolved_config((invalid,))


def test_serialization_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    config = ResolvedConfig.model_validate(
        {"z": 1, "project": {"name": "demo", "seed": 3}, "a": {"x": True}}
    )
    yaml_text = serialize_resolved_config(config)
    json_text = serialize_resolved_config(config, format="json")
    assert yaml_text == serialize_resolved_config(config)
    assert yaml_text.index("a:") < yaml_text.index("project:") < yaml_text.index("z:")
    assert json.loads(json_text)["project"]["seed"] == 3
    with pytest.raises(ConfigError, match="Unsupported"):
        serialize_resolved_config(config, format="toml")
    output = tmp_path / "resolved.yaml"
    dump_resolved_config(config, output)
    assert load_resolved_config((output,)).model_dump() == config.model_dump()
    with pytest.raises(ConfigError, match="Unable to write"):
        dump_resolved_config(config, tmp_path / "missing" / "resolved.yaml")


def test_cli_resolve_prints_output_and_reports_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_yaml(tmp_path / "cli.yaml", "project:\n  name: cli\n")
    assert main(["config", "resolve", str(path), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["project"]["name"] == "cli"

    bad = write_yaml(tmp_path / "cli-bad.yaml", "value: ${NO_SUCH_VALUE}\n")
    assert main(["config", "resolve", str(bad)]) == 2
    assert "error:" in capsys.readouterr().err
