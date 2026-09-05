"""Versioned, fingerprinted persistence for fitted scorer models."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from abrex.features import FeatureSchema
from abrex.registry import Registry
from abrex.scorers.base import (
    PersistableScorer,
    Scorer,
    ScorerArtifact,
)
from abrex.scorers.execution import ScorerExecutor


class ScorerArtifactError(ValueError):
    """Raised when a model or its reproducibility manifest is invalid."""


def fingerprint_feature_schema(schema: FeatureSchema) -> str:
    """Fingerprint the ordered feature schema used by a scorer."""

    payload = json.dumps(
        schema.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return _sha256(payload.encode("utf-8"))


def write_scorer_artifact(
    executor: ScorerExecutor,
    path: Path,
    *,
    feature_schema: FeatureSchema,
    seed: int | None = None,
    feature_config_fingerprint: str | None = None,
) -> ScorerArtifact:
    """Persist model state and a sidecar manifest with content fingerprints."""

    scorer = executor.scorer
    if not isinstance(scorer, PersistableScorer):
        raise ScorerArtifactError(
            f"Scorer {executor.identity!r} does not implement save/load"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        scorer.save(path)
        model_fingerprint = _fingerprint_file(path)
        artifact = ScorerArtifact(
            scorer_key=executor.identity,
            scorer_version=executor.version,
            model_fingerprint=model_fingerprint,
            feature_schema_fingerprint=fingerprint_feature_schema(feature_schema),
            feature_config_fingerprint=(
                feature_config_fingerprint
                if feature_config_fingerprint is not None
                else executor.feature_config_fingerprint
            ),
            seed=executor.seed if seed is None else seed,
            calibration=_strategy_metadata(executor.calibrator),
            selection=_strategy_metadata(executor.selection_policy),
        )
        _write_manifest(_manifest_path(path), artifact)
        return artifact
    except (OSError, TypeError, ValueError) as error:
        raise ScorerArtifactError(
            f"Unable to write scorer artifact {path}: {error}"
        ) from error


def load_scorer_artifact(
    path: Path,
    *,
    registry: Registry[Scorer],
    scorer_params: dict[str, object] | None = None,
    expected_feature_schema_fingerprint: str | None = None,
) -> tuple[ScorerExecutor, ScorerArtifact]:
    """Load and verify a persisted scorer through the supplied registry."""

    try:
        manifest = _read_manifest(_manifest_path(path))
        if manifest.model_fingerprint != _fingerprint_file(path):
            raise ScorerArtifactError(
                "Scorer model fingerprint does not match manifest"
            )
        if (
            expected_feature_schema_fingerprint is not None
            and manifest.feature_schema_fingerprint
            != expected_feature_schema_fingerprint
        ):
            raise ScorerArtifactError(
                "Scorer feature schema does not match expected schema"
            )
        entry = registry.get_entry(manifest.scorer_key)
        scorer = entry.factory(**(scorer_params or {}))
        if not isinstance(scorer, PersistableScorer):
            raise ScorerArtifactError("Registered scorer does not implement save/load")
        scorer.load(path)
        if scorer.version != manifest.scorer_version:
            raise ScorerArtifactError("Scorer version does not match manifest")
        return (
            ScorerExecutor(
                scorer,
                scorer_key=entry.key,
                feature_config_fingerprint=manifest.feature_config_fingerprint,
            ),
            manifest,
        )
    except ScorerArtifactError:
        raise
    except (OSError, TypeError, ValueError, KeyError) as error:
        raise ScorerArtifactError(
            f"Unable to load scorer artifact {path}: {error}"
        ) from error


def _manifest_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.manifest.json")


def _write_manifest(path: Path, artifact: ScorerArtifact) -> None:
    path.write_text(
        json.dumps(artifact.as_dict(), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_manifest(path: Path) -> ScorerArtifact:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ScorerArtifactError("Scorer manifest root must be an object")
    scorer_data = data.get("scorer")
    if not isinstance(scorer_data, dict):
        raise ScorerArtifactError("Scorer manifest scorer must be an object")
    calibration = _metadata_pair(data.get("calibration"), "calibration")
    selection = _metadata_pair(data.get("selection"), "selection")
    seed = data.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ScorerArtifactError("Scorer manifest seed must be an integer or null")
    model_fingerprint = data.get("model_fingerprint")
    schema_fingerprint = data.get("feature_schema_fingerprint")
    if not isinstance(model_fingerprint, str) or not isinstance(
        schema_fingerprint, str
    ):
        raise ScorerArtifactError("Scorer manifest fingerprints must be strings")
    return ScorerArtifact(
        scorer_key=_string(scorer_data, "key"),
        scorer_version=_string(scorer_data, "version"),
        model_fingerprint=model_fingerprint,
        feature_schema_fingerprint=schema_fingerprint,
        feature_config_fingerprint=_optional_string(data, "feature_config_fingerprint"),
        seed=seed,
        calibration=calibration,
        selection=selection,
        schema_version=cast(str, data.get("schema_version")),
    )


def _metadata_pair(value: object, name: str) -> tuple[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ScorerArtifactError(f"{name} metadata must be an object or null")
    return _string(value, "key"), _string(value, "version")


def _string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScorerArtifactError(f"Scorer manifest {key} must be a non-empty string")
    return value


def _optional_string(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ScorerArtifactError(f"Scorer manifest {key} must be a string or null")
    return value


def _strategy_metadata(strategy: object) -> tuple[str, str] | None:
    if strategy is None:
        return None
    identity = getattr(strategy, "identity", None)
    version = getattr(strategy, "version", None)
    if not isinstance(identity, str) or not isinstance(version, str):
        raise TypeError("Strategy metadata requires identity and version")
    return identity, version


def _fingerprint_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "ScorerArtifactError",
    "fingerprint_feature_schema",
    "load_scorer_artifact",
    "write_scorer_artifact",
]
