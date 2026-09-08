from pathlib import Path

import pytest

from abrex.experiments.iteration import (
    IterationController,
    IterationControllerConfig,
    IterationStage,
)


def _stage(
    name: str, evidence: tuple[str, ...] = (), gain: float = 1.0
) -> IterationStage:
    return IterationStage(name, "a" * 64, evidence, evidence, 0.9, gain)


def test_iteration_checkpoints_reject_self_support_and_rolls_back(
    tmp_path: Path,
) -> None:
    controller = IterationController(
        IterationControllerConfig(max_iterations=2), tmp_path / "state.json"
    )
    manifest = controller.run(
        {"resource": "one"},
        (
            (_stage("evidence", ("e1",)), _stage("model", gain=0.2)),
            (_stage("pattern", ("e1",)),),
        ),
        document_count=1,
    )
    assert manifest.rejected == (
        (2, "pattern", "duplicate or self-supporting evidence"),
    )
    assert controller.rollback(manifest)[0].name == "evidence"
    assert controller._read() == manifest


def test_changed_input_invalidates_resume(tmp_path: Path) -> None:
    controller = IterationController(
        IterationControllerConfig(), tmp_path / "state.json"
    )
    controller.run({"resource": "one"}, ((_stage("evidence"),),), document_count=1)
    with pytest.raises(ValueError, match="changed input"):
        controller.run({"resource": "two"}, ((_stage("evidence"),),), document_count=1)
