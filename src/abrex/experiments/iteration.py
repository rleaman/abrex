"""Bounded, resumable controller for evidence/model iteration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field


class IterationControllerConfig(BaseModel):
    """Hard limits and explicit development stopping guards."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_iterations: int = Field(default=2, ge=1, le=100)
    max_documents: int = Field(default=10_000, ge=1)
    max_stages: int = Field(default=20, ge=1)
    minimum_gain: float = 0.0
    minimum_development_precision: float = Field(default=0.0, ge=0, le=1)


@dataclass(frozen=True, slots=True)
class IterationStage:
    """One immutable output stage in an iteration DAG."""

    name: str
    payload_fingerprint: str
    parent_fingerprints: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    development_precision: float = 1.0
    development_gain: float = 0.0

    def __post_init__(self) -> None:
        if self.name not in {"evidence", "dictionary", "pattern", "label", "model"}:
            raise ValueError("unsupported iteration stage")
        if len(self.payload_fingerprint) != 64:
            raise ValueError("stage payload fingerprint must be SHA-256")
        if not 0 <= self.development_precision <= 1:
            raise ValueError("development precision must be between zero and one")


@dataclass(frozen=True, slots=True)
class IterationManifest:
    """Persisted controller state, including all accepted and rejected stages."""

    input_fingerprint: str
    completed_iterations: int
    accepted: tuple[tuple[int, IterationStage], ...]
    rejected: tuple[tuple[int, str, str], ...]
    stopped_reason: str | None
    best_iteration: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "iteration-manifest-v1",
            "input_fingerprint": self.input_fingerprint,
            "completed_iterations": self.completed_iterations,
            "accepted": [
                {"iteration": iteration, "stage": _stage_dict(stage)}
                for iteration, stage in self.accepted
            ],
            "rejected": [
                {"iteration": iteration, "stage": stage, "reason": reason}
                for iteration, stage, reason in self.rejected
            ],
            "stopped_reason": self.stopped_reason,
            "best_iteration": self.best_iteration,
        }


class IterationController:
    """Execute supplied stage plans with deterministic guards and checkpoints."""

    def __init__(self, config: IterationControllerConfig, state_path: Path) -> None:
        self.config = config
        self.state_path = state_path

    def run(
        self,
        input_snapshot: object,
        plans: tuple[tuple[IterationStage, ...], ...],
        *,
        document_count: int,
    ) -> IterationManifest:
        """Run or resume a finite plan; no stage is implicitly regenerated."""

        if document_count > self.config.max_documents:
            return self._checkpoint(
                _manifest(
                    self._input(input_snapshot), 0, (), (), "document limit", None
                )
            )
        input_fingerprint = self._input(input_snapshot)
        existing = self._read()
        if existing is not None and existing.input_fingerprint != input_fingerprint:
            raise ValueError("changed input snapshot invalidates iteration state")
        accepted = list(existing.accepted if existing else ())
        rejected = list(existing.rejected if existing else ())
        start = (existing.completed_iterations if existing else 0) + 1
        best_iteration = existing.best_iteration if existing else None
        best_gain = max(
            (stage.development_gain for _, stage in accepted), default=float("-inf")
        )
        stopped_reason: str | None = None
        for iteration in range(start, min(len(plans), self.config.max_iterations) + 1):
            plan = plans[iteration - 1]
            if len(plan) + len(accepted) > self.config.max_stages:
                stopped_reason = "stage limit"
                break
            iteration_gain = max(
                (stage.development_gain for stage in plan), default=0.0
            )
            if iteration > 1 and iteration_gain <= self.config.minimum_gain:
                stopped_reason = "no development gain"
                break
            seen_evidence = {
                evidence_id
                for _, stage in accepted
                for evidence_id in stage.evidence_ids
            }
            for stage in plan:
                reason = self._reject_reason(stage, seen_evidence)
                if reason is not None:
                    rejected.append((iteration, stage.name, reason))
                    continue
                accepted.append((iteration, stage))
                seen_evidence.update(stage.evidence_ids)
            if iteration_gain > best_gain and all(
                stage.development_precision >= self.config.minimum_development_precision
                for stage in plan
            ):
                best_gain, best_iteration = iteration_gain, iteration
            self._checkpoint(
                _manifest(
                    input_fingerprint,
                    iteration,
                    tuple(accepted),
                    tuple(rejected),
                    None,
                    best_iteration,
                )
            )
        if stopped_reason is None and len(plans) > self.config.max_iterations:
            stopped_reason = "iteration limit"
        result = _manifest(
            input_fingerprint,
            min(len(plans), self.config.max_iterations),
            tuple(accepted),
            tuple(rejected),
            stopped_reason,
            best_iteration,
        )
        return self._checkpoint(result)

    def rollback(self, manifest: IterationManifest) -> tuple[IterationStage, ...]:
        """Return only stages from the best development-selected iteration."""

        if manifest.best_iteration is None:
            return ()
        return tuple(
            stage
            for iteration, stage in manifest.accepted
            if iteration == manifest.best_iteration
        )

    def _reject_reason(
        self, stage: IterationStage, seen_evidence: set[str]
    ) -> str | None:
        if stage.evidence_ids and any(
            item in seen_evidence for item in stage.evidence_ids
        ):
            return "duplicate or self-supporting evidence"
        if stage.development_precision < self.config.minimum_development_precision:
            return "development precision guard"
        return None

    @staticmethod
    def _input(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, default=str).encode()
        ).hexdigest()

    def _checkpoint(self, manifest: IterationManifest) -> IterationManifest:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".part")
        temporary.write_text(
            json.dumps(manifest.as_dict(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
        return manifest

    def _read(self) -> IterationManifest | None:
        if not self.state_path.exists():
            return None
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        accepted = tuple(
            (int(item["iteration"]), _stage(item["stage"])) for item in data["accepted"]
        )
        rejected = tuple(
            (int(item["iteration"]), str(item["stage"]), str(item["reason"]))
            for item in data["rejected"]
        )
        return _manifest(
            data["input_fingerprint"],
            int(data["completed_iterations"]),
            accepted,
            rejected,
            data.get("stopped_reason"),
            data.get("best_iteration"),
        )


def _stage_dict(stage: IterationStage) -> dict[str, object]:
    return {
        "name": stage.name,
        "payload_fingerprint": stage.payload_fingerprint,
        "parent_fingerprints": list(stage.parent_fingerprints),
        "evidence_ids": list(stage.evidence_ids),
        "development_precision": stage.development_precision,
        "development_gain": stage.development_gain,
    }


def _stage(data: dict[str, object]) -> IterationStage:
    return IterationStage(
        str(data["name"]),
        str(data["payload_fingerprint"]),
        tuple(str(item) for item in cast(list[object], data["parent_fingerprints"])),
        tuple(str(item) for item in cast(list[object], data["evidence_ids"])),
        float(cast(float, data["development_precision"])),
        float(cast(float, data["development_gain"])),
    )


def _manifest(
    input_fingerprint: str,
    completed: int,
    accepted: tuple[tuple[int, IterationStage], ...],
    rejected: tuple[tuple[int, str, str], ...],
    stopped: str | None,
    best: int | None,
) -> IterationManifest:
    return IterationManifest(
        input_fingerprint, completed, accepted, rejected, stopped, best
    )


__all__ = [
    "IterationController",
    "IterationControllerConfig",
    "IterationManifest",
    "IterationStage",
]
