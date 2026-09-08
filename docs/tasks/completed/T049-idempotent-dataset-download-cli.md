# T049 completion: idempotent dataset download CLI

Implemented the selective, idempotent and group-driven historical dataset
download workflow.

Changed:

- Added typed download groups, per-item planning/results, version-2 provenance,
  deterministic file/tree fingerprints, conflict handling, safe forced
  replacement and dry-run support in `src/abrex/tools/download_datasets.py`.
- Added `datasets download --config`, `datasets download-all --group`,
  `--groups-config`, `--dry-run` and `--force`, while retaining the positional
  aggregate-manifest syntax.
- Added seven corpus-aligned bundle files under `configs/datasets/` and the
  `historical` group in `configs/dataset-groups.yaml`.
- Updated the README and historical-download documentation.

Compatibility decisions:

- `downloads.overwrite` remains accepted for old manifests and acts as the
  legacy force setting; new invocations should use explicit `--force`.
- `configs/historical-datasets.yaml` remains the bounded legacy aggregate
  manifest. New source definitions are maintained in the per-bundle files and
  selected by the group manifest; the legacy form is not used by the new group
  command.
- Legacy plain-file sidecars are verified against their recorded file digest.
  Legacy extracted-directory sidecars are migrated with a baseline tree
  fingerprint and `archive_sha256_verified: false`; they are not treated as
  archive-checksum verified.

Verification:

- `ruff format` and `ruff check` passed for the changed Python modules.
- `mypy` passed for the changed Python modules.
- The historical group resolved offline to 7 bundles and 11 source items.
- Both new command help forms and the historical dry run completed without
  network requests or destination writes in the existing partially populated
  workspace.
- `git diff --check` passed.

The repository pytest invocation could not complete because the managed
Windows environment denied pytest cleanup access to both the repository and
system temporary directories (`WinError 5`). Existing historical artifacts
were used only for the non-mutating dry-run check. No live historical download
was run.

Next ready task: T041, resumable bounded corpus processing.
