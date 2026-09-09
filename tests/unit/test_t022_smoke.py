from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from abrex.corpora import read_canonical_dataset


def test_t022_smoke_materializer_writes_auditable_slice(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    output_jsonl = tmp_path / "smoke.jsonl"
    output_manifest = tmp_path / "smoke.manifest.json"
    environment = os.environ.copy()
    source = str(root / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = source + (os.pathsep + existing if existing else "")
    completed = subprocess.run(
        (
            sys.executable,
            str(root / "scripts" / "materialize_t022_smoke.py"),
            "--source-jsonl",
            str(root / "docs" / "examples" / "experiment-corpus.jsonl"),
            "--source-manifest",
            str(root / "docs" / "examples" / "experiment-corpus.manifest.json"),
            "--output-jsonl",
            str(output_jsonl),
            "--output-manifest",
            str(output_manifest),
            "--count",
            "1",
            "--seed",
            "t022-test",
        ),
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    records, manifest = read_canonical_dataset(output_jsonl, output_manifest)
    selection = json.loads(output_manifest.read_text(encoding="utf-8"))["selection"]
    source_manifest = json.loads(
        (root / "docs" / "examples" / "experiment-corpus.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(records) == 1
    assert manifest.fingerprint == json.loads(completed.stdout)["fingerprint"]
    assert selection["full_dataset_fingerprint"] == source_manifest["fingerprint"]
    assert selection["eligible_record_count_in_full_dataset"] == 2
    assert len(selection["record_ids"]) == 1
