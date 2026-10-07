"""Create a deterministic, gold-free Milestone C Linux bundle archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections.abc import Sequence
from pathlib import Path

FIXED_TIMESTAMP = (2026, 10, 7, 0, 0, 0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def package(bundle: Path, archive: Path, manifest_path: Path) -> dict[str, object]:
    """Archive one inspected job bundle with stable ordering and metadata."""

    bundle_manifest_path = bundle / "bundle.json"
    raw_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_manifest, dict) or not isinstance(
        raw_manifest.get("bundle_id"), str
    ):
        raise ValueError("bundle.json does not contain a bundle_id")

    files = tuple(sorted(path for path in bundle.rglob("*") if path.is_file()))
    forbidden_names = tuple(
        path.relative_to(bundle).as_posix()
        for path in files
        if path.name.casefold().startswith("strict-gold")
        or ".annotations." in path.name.casefold()
    )
    if forbidden_names:
        raise ValueError(
            f"gold/review files cannot enter the bundle: {forbidden_names}"
        )

    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as output:
        for path in files:
            relative = path.relative_to(bundle).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if path.suffix == ".sh" else 0o644
            info.external_attr = mode << 16
            output.writestr(info, path.read_bytes(), compresslevel=9)

    result: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-linux-bundle-release-v1",
        "bundle_id": raw_manifest["bundle_id"],
        "source_directory": bundle.as_posix(),
        "archive_path": archive.as_posix(),
        "archive_sha256": _sha256(archive),
        "archive_bytes": archive.stat().st_size,
        "files": len(files),
        "gold_annotations_included": False,
        "prediction_documents": 120,
        "jobs": [
            "campaign-2026-10-milestone-c-ab3p-linux",
            "campaign-2026-10-milestone-c-plodv2-pairing-linux",
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path(".artifacts/campaign-2026-10/milestone-c/linux-bundle-v1"),
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path(
            ".artifacts/campaign-2026-10/milestone-c/"
            "abrex-milestone-c-linux-bundle-v1.zip"
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/linux-bundle-release-v1.json"
        ),
    )
    args = parser.parse_args(argv)
    result = package(args.bundle, args.archive, args.manifest)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
