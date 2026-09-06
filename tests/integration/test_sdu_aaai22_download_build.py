"""End-to-end coverage for the official SDU@AAAI-22 AE archive layout."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

import abrex.cli as cli
from abrex.corpora import read_canonical_jsonl

OFFICIAL_ARCHIVE_URL = (
    "https://github.com/amirveyseh/AAAI-22-SDU-shared-task-1-AE/"
    "archive/refs/heads/main.zip"
)
ARCHIVE_ROOT = "AAAI-22-SDU-shared-task-1-AE-main"


class _ArchiveResponse:
    def __init__(self, content: bytes) -> None:
        self.stream = io.BytesIO(content)

    def __enter__(self) -> _ArchiveResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)


def _synthetic_github_archive() -> bytes:
    """Create GitHub's ``<repo>-main/`` archive shape from official fields."""

    text = "Alpha (A) and Beta (B)"
    rows = [
        {
            "ID": "official-schema-1",
            "text": text,
            "acronyms": [
                [text.index("A"), text.index("A") + 1],
                [text.index("B"), text.index("B") + 1],
            ],
            "long-forms": [[0, 5]],
        }
    ]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(f"{ARCHIVE_ROOT}/README.md", "SDU@AAAI-22 AE\n")
        archive.writestr(
            f"{ARCHIVE_ROOT}/scorer.py",
            "record['ID']; record['acronyms']; record['long-forms']\n",
        )
        archive.writestr(
            f"{ARCHIVE_ROOT}/data/english/scientific/train.json",
            json.dumps(rows),
        )
    return output.getvalue()


def test_sdu_aaai22_archive_download_then_corpus_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive = _synthetic_github_archive()
    requested_urls: list[str] = []

    def urlopen(request: Any, timeout: float) -> _ArchiveResponse:
        requested_urls.append(request.full_url)
        return _ArchiveResponse(archive)

    monkeypatch.setattr("abrex.tools.download_datasets.urllib.request.urlopen", urlopen)

    raw_destination = tmp_path / "raw" / "sdu_aaai22"
    download_config = tmp_path / "downloads.yaml"
    download_config.write_text(
        f"""
downloads:
  retries: 0
  polite_delay_seconds: 0
  datasets:
    - name: sdu_aaai22_repository
      url: {OFFICIAL_ARCHIVE_URL}
      destination: {raw_destination.as_posix()}
      extract: true
""",
        encoding="utf-8",
    )

    assert cli.main(["datasets", "download", str(download_config)]) == 0
    capsys.readouterr()
    assert requested_urls == [OFFICIAL_ARCHIVE_URL]

    source = raw_destination / ARCHIVE_ROOT / "data/english/scientific/train.json"
    assert source.is_file()

    output_directory = tmp_path / "processed" / "sdu_aaai22_ae"
    corpus_config = tmp_path / "sdu_aaai22_ae.yaml"
    corpus_config.write_text(
        f"""
corpus:
  adapter:
    type: sdu_aaai22_ae
    params: {{}}
  source:
    identifier: synthetic-sdu-aaai22-ae
    location: {source.as_posix()}
    format: json
  normalizers:
    - type: identity
      params: {{}}
  strict: true
  output:
    directory: {output_directory.as_posix()}
""",
        encoding="utf-8",
    )

    assert cli.main(["corpus", "build", "--config", str(corpus_config)]) == 0
    capsys.readouterr()

    records = read_canonical_jsonl(output_directory / "canonical.jsonl")
    assert len(records) == 1
    assert records[0].id == "official-schema-1"
    assert len(records[0].gold_annotations) == 3
    assert records[0].gold_annotations[0].short_form_text == "A"
    assert records[0].gold_annotations[2].long_form_text == "Alpha"
