from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from abrex.corpora import (
    build_dataset_manifest,
    write_canonical_jsonl,
)
from abrex.corpora.validation import ValidationSummary
from abrex.domain import AbbreviationDefinition, CorpusRecord, Document, TextSpan
from abrex.jobs import JobResultManifest
from abrex.literature import fresh_evaluation, fresh_readout
from abrex.literature.fresh_evaluation import materialize_fresh_projection
from abrex.literature.fresh_readout import materialize_fresh_readout, method_summary
from abrex.resolvers import (
    PredictionArtifact,
    PredictionRecord,
    ResolverMetadata,
    write_prediction_artifact,
)

ROOT = Path(__file__).resolve().parents[2]


def test_real_t067_projection_is_gold_separated_and_immutable(tmp_path: Path) -> None:
    output = tmp_path / "T067"
    result = _project(output)

    assert len(result.prediction_records) == 32
    assert all(not record.gold_annotations for record in result.prediction_records)
    assert sum(len(record.gold_annotations) for record in result.gold_records) == 32
    assert result.ledger["counts"] == {
        "cases": 32,
        "article_groups": 8,
        "strict_relations": 32,
        "diagnostic_relations": 8,
        "unresolved_relations": 0,
        "prose_cases": 24,
        "table_or_list_cases": 8,
        "empty_strict_cases": 25,
    }
    prediction_text = (output / "prediction.jsonl").read_text(encoding="utf-8")
    assert '"gold_annotations":[]' in prediction_text
    assert all(
        not json.loads(line)["gold_annotations"]
        for line in prediction_text.splitlines()
    )

    lock_data = json.loads(
        (
            ROOT
            / "evidence/T066/review-packet-blind-v1.annotations.corrected-v2.lock.json"
        ).read_text(encoding="utf-8")
    )
    lock_data["locked_at"] = "tampered"
    bad_lock = tmp_path / "bad-lock.json"
    bad_lock.write_text(json.dumps(lock_data), encoding="utf-8")
    with pytest.raises(ValueError, match="correction manifest mismatch"):
        _project(tmp_path / "bad", lock_path=bad_lock)


def test_method_summary_counts_duplicates_and_empty_passage_errors() -> None:
    strict = {("gold", 0, 1, 2, 6)}
    diagnostic = {("empty", 0, 1, 2, 6)}
    predictions = [
        ("gold", 0, 1, 2, 6),
        ("gold", 0, 1, 2, 6),
        ("empty", 0, 1, 2, 6),
        ("empty", 7, 8, 9, 10),
    ]

    summary = method_summary(
        predictions, strict, diagnostic, case_ids={"gold", "empty"}
    )

    assert summary["true_positives"] == 1
    assert summary["duplicate_predictions"] == 1
    assert summary["outside_strict_target"] == 1
    assert summary["false_positives"] == 2
    assert summary["empty_passage_false_positives"] == 1
    assert summary["empty_passage_outside_target_matches"] == 1


def test_fresh_readout_scores_union_and_refuses_rewrite(tmp_path: Path) -> None:
    prediction_records = (
        CorpusRecord(Document("d1", "alpha beta (AB)"), record_id="d1"),
        CorpusRecord(Document("d2", "other name (ON)"), record_id="d2"),
    )
    gold_records = (
        CorpusRecord(
            Document("d1", "alpha beta (AB)"),
            (
                AbbreviationDefinition(
                    "d1",
                    short_form=TextSpan(12, 14),
                    long_form=TextSpan(0, 10),
                    short_form_text="AB",
                    long_form_text="alpha beta",
                ),
            ),
            record_id="d1",
        ),
        CorpusRecord(Document("d2", "other name (ON)"), record_id="d2"),
    )
    prediction_path, prediction_manifest = _dataset(
        tmp_path, "prediction", prediction_records
    )
    gold_path, gold_manifest = _dataset(tmp_path, "gold", gold_records)
    dataset_fingerprint = build_dataset_manifest(
        prediction_records, dataset_id="unused"
    ).fingerprint
    ledger = {
        "policy_id": "t057-strict-exact-pair-v1",
        "content_sha256": "a" * 64,
        "counts": {"cases": 2, "strict_relations": 1},
        "cases": [
            {
                "case_id": "d1",
                "article_group_id": "g1",
                "evaluation_arm": "prose",
                "relations": [],
            },
            {
                "case_id": "d2",
                "article_group_id": "g2",
                "evaluation_arm": "table_or_list",
                "relations": [
                    {
                        "disposition": "diagnostic",
                        "short_form": {"start": 12, "end": 14},
                        "long_form": {"start": 0, "end": 10},
                    }
                ],
            },
        ],
    }
    ledger_path = tmp_path / "ledger.json"
    _json(ledger_path, ledger)
    run_manifest_path = tmp_path / "run.json"
    _json(
        run_manifest_path,
        {
            "status": "inputs_frozen_predictions_pending",
            "datasets": {
                "prediction_input": {
                    "fingerprint": dataset_fingerprint,
                    "gold_annotations": 0,
                }
            },
            "eligibility_ledger": {"content_sha256": "a" * 64},
        },
    )
    prediction_paths: dict[str, Path] = {}
    result_paths: dict[str, Path] = {}
    for name, definitions in {
        "schwartz_hearst": (
            AbbreviationDefinition(
                "d1", TextSpan(12, 14), TextSpan(0, 10), "AB", "alpha beta"
            ),
        ),
        "plodv2_pairing": (
            AbbreviationDefinition(
                "d2", TextSpan(12, 14), TextSpan(0, 10), "ON", "other name"
            ),
        ),
    }.items():
        predictions = tmp_path / name / "predictions.jsonl"
        predictions.parent.mkdir()
        write_prediction_artifact(
            PredictionArtifact(
                ResolverMetadata(name, "test"),
                (
                    PredictionRecord(
                        "d1", definitions if name == "schwartz_hearst" else ()
                    ),
                    PredictionRecord(
                        "d2", definitions if name == "plodv2_pairing" else ()
                    ),
                ),
                dataset_fingerprint=dataset_fingerprint,
            ),
            predictions,
        )
        result = JobResultManifest(
            result_id=("b" if name == "schwartz_hearst" else "c") * 64,
            bundle_id="d" * 64,
            job_id=name.replace("_", "-"),
            status="complete",
            started_utc="2026-10-05T00:00:00+00:00",
            completed_utc="2026-10-05T00:00:01+00:00",
            elapsed_seconds=1.0,
            dataset_fingerprint=dataset_fingerprint,
            documents_fingerprint="e" * 64,
            resolver={"key": name, "version": "test"},
            environment={},
            files={"predictions.jsonl": _sha256(predictions)},
        )
        result_path = predictions.parent / "result.json"
        result_path.write_text(result.model_dump_json(), encoding="utf-8")
        prediction_paths[name] = predictions
        result_paths[name] = result_path

    report_path = tmp_path / "report.json"
    report = materialize_fresh_readout(
        prediction_corpus_path=prediction_path,
        prediction_corpus_manifest_path=prediction_manifest,
        gold_corpus_path=gold_path,
        gold_corpus_manifest_path=gold_manifest,
        ledger_path=ledger_path,
        run_manifest_path=run_manifest_path,
        prediction_paths=prediction_paths,
        result_paths=result_paths,
        report_path=report_path,
        report_markdown_path=tmp_path / "report.md",
        disposition_path=tmp_path / "dispositions.jsonl",
    )
    assert report["status"] == "fail"
    comparison = report["comparison"]
    assert isinstance(comparison, dict)
    assert comparison["unique_correct_additions"] == 0
    materialize_fresh_readout(
        prediction_corpus_path=prediction_path,
        prediction_corpus_manifest_path=prediction_manifest,
        gold_corpus_path=gold_path,
        gold_corpus_manifest_path=gold_manifest,
        ledger_path=ledger_path,
        run_manifest_path=run_manifest_path,
        prediction_paths=prediction_paths,
        result_paths=result_paths,
        report_path=report_path,
        report_markdown_path=tmp_path / "report.md",
        disposition_path=tmp_path / "dispositions.jsonl",
    )
    report_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        materialize_fresh_readout(
            prediction_corpus_path=prediction_path,
            prediction_corpus_manifest_path=prediction_manifest,
            gold_corpus_path=gold_path,
            gold_corpus_manifest_path=gold_manifest,
            ledger_path=ledger_path,
            run_manifest_path=run_manifest_path,
            prediction_paths=prediction_paths,
            result_paths=result_paths,
            report_path=report_path,
            report_markdown_path=tmp_path / "report.md",
            disposition_path=tmp_path / "dispositions.jsonl",
        )


def test_t067_preflight_rejects_changed_scientific_inputs(tmp_path: Path) -> None:
    protocol_path = ROOT / "docs/artifacts/T063-decision-prefill.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    blind = {
        "candidate_generators_run": False,
        "evaluated_methods_run": False,
        "predictions_exposed": False,
        "token_enrichment_used": False,
    }
    with pytest.raises(ValueError, match="prediction blindness"):
        fresh_evaluation._validate_blind_source(  # noqa: SLF001
            {"blindness": {**blind, "predictions_exposed": True}},
            protocol_path,
            protocol,
        )
    with pytest.raises(ValueError, match="lacks configuration"):
        fresh_evaluation._validate_blind_source(  # noqa: SLF001
            {"blindness": blind}, protocol_path, protocol
        )
    with pytest.raises(ValueError, match="different T063"):
        fresh_evaluation._validate_blind_source(  # noqa: SLF001
            {"blindness": blind, "config": {"protocol_sha256": "bad"}},
            protocol_path,
            protocol,
        )
    with pytest.raises(ValueError, match="not approved"):
        fresh_evaluation._validate_blind_source(  # noqa: SLF001
            {
                "blindness": blind,
                "config": {"protocol_sha256": _sha256(protocol_path)},
            },
            protocol_path,
            {"status": "draft"},
        )

    with pytest.raises(ValueError, match="lacks corrected identities"):
        fresh_evaluation._validate_correction_files(  # noqa: SLF001
            {}, protocol_path, protocol_path
        )
    with pytest.raises(ValueError, match="not recorded as prediction-blind"):
        fresh_evaluation._validate_correction_files(  # noqa: SLF001
            {
                "corrected": {
                    "state_file_sha256": _sha256(protocol_path),
                    "lock_file_sha256": _sha256(protocol_path),
                },
                "exposure": {},
            },
            protocol_path,
            protocol_path,
        )

    with pytest.raises(ValueError, match="lacks frozen components"):
        fresh_evaluation._validate_protocol_components({}, {})  # noqa: SLF001
    with pytest.raises(ValueError, match="supplied T067 components"):
        fresh_evaluation._validate_protocol_components(  # noqa: SLF001
            protocol,
            {"schwartz_hearst": ROOT / "configs/experiments/T060-schwartz-hearst.yaml"},
        )
    changed = tmp_path / "changed.yaml"
    changed.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="configuration changed"):
        fresh_evaluation._validate_protocol_components(  # noqa: SLF001
            protocol,
            {
                "schwartz_hearst": changed,
                "plodv2_pairing": ROOT / "configs/experiments/T060-plodv2-linux.yaml",
            },
        )
    array_path = tmp_path / "array.json"
    array_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object required"):
        fresh_evaluation._read_object(array_path)  # noqa: SLF001


def test_t067_readout_rejects_changed_frozen_manifest(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    _json(ledger_path, {"content_sha256": "ledger"})
    with pytest.raises(ValueError, match="not the frozen"):
        fresh_readout._validate_run_inputs({}, ledger_path, "data")  # noqa: SLF001
    base = {
        "status": "inputs_frozen_predictions_pending",
        "datasets": {
            "prediction_input": {"fingerprint": "data", "gold_annotations": 0}
        },
        "eligibility_ledger": {"content_sha256": "ledger"},
    }
    with pytest.raises(ValueError, match="dataset differs"):
        fresh_readout._validate_run_inputs(  # noqa: SLF001
            {**base, "datasets": {}}, ledger_path, "data"
        )
    with pytest.raises(ValueError, match="not gold-free"):
        fresh_readout._validate_run_inputs(  # noqa: SLF001
            {
                **base,
                "datasets": {
                    "prediction_input": {
                        "fingerprint": "data",
                        "gold_annotations": 1,
                    }
                },
            },
            ledger_path,
            "data",
        )
    with pytest.raises(ValueError, match="ledger differs"):
        fresh_readout._validate_run_inputs(  # noqa: SLF001
            {**base, "eligibility_ledger": {"content_sha256": "changed"}},
            ledger_path,
            "data",
        )


def _project(output: Path, *, lock_path: Path | None = None):  # type: ignore[no-untyped-def]
    return materialize_fresh_projection(
        packet_path=ROOT / "evidence/T065/review-packet-blind-v1.json",
        state_path=(
            ROOT / "evidence/T066/review-packet-blind-v1.annotations.corrected-v2.json"
        ),
        lock_path=lock_path
        or ROOT
        / "evidence/T066/review-packet-blind-v1.annotations.corrected-v2.lock.json",
        correction_manifest_path=ROOT / "evidence/T066/correction-manifest-v2.json",
        source_manifest_path=ROOT / "evidence/T065/source-manifest-v1.json",
        protocol_path=ROOT / "docs/artifacts/T063-decision-prefill.json",
        component_config_paths={
            "schwartz_hearst": ROOT / "configs/experiments/T060-schwartz-hearst.yaml",
            "plodv2_pairing": ROOT / "configs/experiments/T060-plodv2-linux.yaml",
        },
        prediction_path=output / "prediction.jsonl",
        prediction_manifest_path=output / "prediction.manifest.json",
        gold_path=output / "gold.jsonl",
        gold_manifest_path=output / "gold.manifest.json",
        ledger_path=output / "ledger.json",
        run_manifest_path=output / "run.json",
    )


def _dataset(
    root: Path, name: str, records: tuple[CorpusRecord, ...]
) -> tuple[Path, Path]:
    path = root / f"{name}.jsonl"
    manifest_path = root / f"{name}.manifest.json"
    write_canonical_jsonl(records, path)
    manifest = build_dataset_manifest(
        records,
        dataset_id=name,
        validation=ValidationSummary(
            records_seen=len(records), records_kept=len(records)
        ),
    )
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    return path, manifest_path


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
