# T049 Make dataset downloads selective, idempotent, and group-driven

Status: Complete. Implemented September 8, 2026. Milestone: maintenance and usability.

## Outcome

Make historical dataset acquisition follow the same user-facing shape as corpus
building: download one corpus/source bundle from its own YAML configuration, or
download every bundle in a named configuration-driven group. A normal rerun
must safely reuse already acquired sources and continue with missing ones,
without requiring the user to edit a combined manifest or enable destructive
overwrite behavior.

The intended commands are:

```console
abrex datasets download --config configs/datasets/ab3p.yaml
abrex datasets download-all --group historical
```

The existing command remains accepted during migration:

```console
python -m abrex datasets download configs/historical-datasets.yaml
```

## Problem and current evidence

The current `configs/historical-datasets.yaml` contains every historical
source. `src/abrex/tools/download_datasets.py::_download_one` raises
`DownloadError` as soon as any destination exists while `overwrite` is false,
and `download_datasets` aborts the sequence on that first error. Consequently,
adding or acquiring one later dataset requires editing the aggregate manifest,
moving existing data, or enabling overwrite for every entry. This is unlike
the existing `corpus build --config ...` and configuration-driven
`corpus build-all --group ...` workflow.

## Dependencies and reading

[T011](T011-historical-corpus-adapters.md) and
[T017](T017-reproducible-development-environments.md).

Read `AGENTS.md`, `START_HERE_FOR_CODEX.md`, the
[Luna execution guide](LUNA_EXECUTION_GUIDE.md), `README.md`,
`docs/historical-downloads.md`, `docs/historical-builds.md`,
`configs/historical-datasets.yaml`, `configs/corpus-groups.yaml`,
`src/abrex/tools/download_datasets.py`, the dataset and corpus command paths in
`src/abrex/cli/__init__.py`, and the corresponding unit/integration tests.
Inspect the current worktree and preserve unrelated user changes.

The BADREX-corrected corpora remain excluded by the settled decision in
`docs/badrex-availability.md`. Do not search for them or add them to the new
download group.

## Required CLI and configuration contract

1. Keep `datasets download` as the one-bundle operation and add the explicit
   `--config PATH` spelling, matching `corpus build --config`. A bundle may
   contain multiple source files when they jointly form one corpus, such as the
   SDU@AAAI-21 train/dev/test files.
2. Add `datasets download-all --group NAME` and a configurable
   `--groups-config` option whose default is a checked-in dataset group
   manifest. Follow the typed, configuration-driven pattern used by corpus
   build groups. Unknown groups must report the available group names.
3. Split the aggregate historical manifest into one checked-in YAML file per
   corpus/source bundle under `configs/datasets/`, and add a `historical` group
   containing all and only the currently supported historical bundles. Keep
   source URLs, destination layouts, extraction flags, user-agent behavior,
   retry policy, and polite request behavior equivalent to the current
   manifest. The group and the corpus-build group should use aligned stable
   names where practical.
4. Retain the positional aggregate-manifest form for backward compatibility
   and document it as legacy syntax. Do not maintain two silently divergent
   authoritative copies of source definitions: choose and document a bounded
   compatibility mechanism, such as a legacy manifest that delegates to or is
   contract-tested against the per-bundle definitions. Do not remove the old
   syntax in this task.
5. Add `--dry-run` to both download commands. It must resolve configuration and
   classify every item without making network requests, writing manifests, or
   changing destinations.
6. Add an explicit CLI `--force` option for intentional replacement. A group
   run must never imply force. Preserve compatibility with the current typed
   `downloads.overwrite` field if it remains supported, define precedence
   unambiguously, and warn/document any deprecation rather than silently
   changing it.

Keep argparse handling thin. Selection, state inspection, downloading, and
batch orchestration belong in typed application/service code, not in CLI
branches. A new registry or plugin system is not needed for a fixed HTTP/file
acquisition workflow.

## Idempotence and safety contract

Implement an explicit per-item state machine and a typed result status. At
minimum it must distinguish `downloaded`, `reused`, `planned`, `conflict`, and
`failed` outcomes.

- If the destination is absent, acquire it through the existing `.part`,
  checksum, safe-extraction, and atomic-publication path.
- If the destination and matching provenance are present and their recorded
  content identity validates, make no request and report `reused` as a normal
  successful outcome.
- If a destination exists without trustworthy matching provenance, if its
  content has changed, or if the current source/extraction configuration does
  not match the recorded identity, report `conflict`; do not overwrite it by
  default. The diagnostic must name the dataset, destination, reason, and the
  explicit `--force` remedy.
- Version the sidecar manifest and record enough canonical acquisition identity
  to decide reuse deterministically: stable source name and URL, destination,
  extraction settings, configured checksum, downloaded-byte SHA-256, and an
  output content identity. For extracted directories, use a deterministic tree
  fingerprint over normalized relative paths and file contents; directory
  modification times and enumeration order must not affect it.
- Handle existing legacy `.download.json` sidecars deliberately. A regular
  file can be checked against its recorded SHA-256. An extracted directory
  cannot be retroactively proven from the deleted archive alone; if matching
  legacy provenance is adopted, calculate and record a baseline tree identity,
  mark/log the legacy migration explicitly, and never call it checksum-verified
  against the archive. A missing or inconsistent sidecar is a conflict.
- `--force` may replace an existing artifact only after the replacement has
  been completely downloaded, checksum-checked, and, where applicable, safely
  extracted in staging. Preserve or restore the old target if preparation or
  publication fails. Never delete all group destinations up front.
- Remove stale task-owned `.part` artifacts safely when starting that same
  item, but do not treat arbitrary sibling files as downloader-owned.

Polite delay applies between actual network requests, not between items that
are reused or classified locally.

## Batch behavior and machine-readable output

Process a group deterministically in declared order. One reused item must not
prevent later missing items from downloading. Continue after an independent
item conflict or download failure so the user gets a complete result for the
requested group, then return the repository's established nonzero operational
failure code if any item failed or conflicted. Configuration errors may fail
before item processing.

Keep stdout machine-readable and stderr for logs. Preserve the successful
legacy command's top-level JSON array shape so existing consumers do not break;
add status and diagnostic fields additively. Emit the same result shape for
single-bundle and group commands, including every requested item in declared
order. Print the result array even when a batch ends nonzero, and log a concise
count summary. Do not include temporary paths or nondeterministic timestamps in
the result contract unless clearly separated from stable identity fields.

## Implementation steps

1. Introduce or extend frozen Pydantic boundary models for one download bundle,
   named download groups, and CLI execution options. Validate duplicate source
   names and duplicate destinations within a resolved operation before any
   network or filesystem mutation.
2. Separate state inspection/planning from execution. Model the action for each
   item so dry runs, normal runs, forced refreshes, and tests share the same
   decision rules.
3. Evolve `DownloadedDataset`/serialization into a typed result contract with
   status and bounded diagnostics while retaining existing successful fields.
   Catch failures at the per-item orchestration boundary; do not introduce a
   broad exception handler inside parsing, hashing, or extraction logic.
4. Implement versioned provenance validation and deterministic file/tree
   fingerprints. Write sidecars atomically after the output is successfully
   published; an incomplete sidecar must never make a partial target reusable.
5. Add the new CLI forms, per-bundle configs, and named group. Use a shared
   single-bundle execution path for `download` and `download-all`, just as
   corpus group builds compose the single-corpus operation.
6. Update `README.md`, `docs/historical-downloads.md`, the returning-user
   quickstart where relevant, command help, and examples. Explain normal rerun,
   dry-run, conflict, force, partial group failure, raw-download versus corpus-
   build separation, and the legacy command's migration status.

## Acceptance criteria

- From a clean fixture workspace, the single-bundle and historical-group forms
  select the intended sources and produce the documented structured results.
- Given a two-item group where the first artifact is valid and already present
  and the second is absent, a normal run makes no request for the first,
  downloads the second, reports `reused` then `downloaded`, and exits zero.
- Repeating a completed command is a no-op apart from local validation and
  logs/results; it neither contacts the network nor changes artifact or
  sidecar content.
- A changed/corrupt artifact, stale source configuration, missing sidecar, or
  duplicate destination is never silently accepted or overwritten. The
  command reports an actionable conflict and nonzero status while still
  processing independent group entries.
- `--force` safely refreshes only the selected conflicting or existing items,
  and a simulated retrieval, checksum, extraction, or publication failure
  leaves the prior artifact usable.
- Dry-run tests prove zero network calls and zero writes for missing, reusable,
  conflicting, and grouped cases.
- Legacy positional syntax still works, and legacy sidecar migration behavior
  is covered for both plain files and extracted directories.
- The checked-in dataset configurations and group are contract-tested against
  expected stable names, unique destinations, supported sources, and corpus
  build inputs. No BADREX-corrected entry is introduced.
- Unit and integration tests require no live network access. Retain the safe ZIP
  and TAR traversal tests and the SDU@AAAI-22 download-to-build regression.

## Verification

Run focused downloader configuration, state-machine, CLI, archive-safety, and
download-to-build tests, then the repository fast quality gate from the Luna
execution guide. Also run:

```powershell
.\env313\Scripts\python.exe -m abrex datasets download --help
.\env313\Scripts\python.exe -m abrex datasets download-all --help
.\env313\Scripts\python.exe -m abrex datasets download-all --group historical --dry-run
git diff --check
```

The historical dry run must be safe in a partially populated local workspace
and must not contact remote servers. Do not run a live full historical download
as an acceptance requirement; mocked/local HTTP fixtures are sufficient for
network behavior, while local existing historical data may be used only for a
non-mutating dry-run check.

## Scope and non-goals

Downloading remains raw-source acquisition only. Do not trigger corpus builds,
change scientific annotation semantics, redesign the literature/resource
acquisition subsystems, add parallel downloading, introduce Python entry-point
plugins, or revisit source availability. Do not opportunistically rename the
established `datasets` command family.

## Deliverables and completion note

Deliver the typed implementation, migrated configuration layout, offline tests,
and updated user documentation. After all acceptance checks pass, write
`docs/tasks/completed/T049-idempotent-dataset-download-cli.md` with files
changed, exact commands/results, compatibility decisions, manifest schema and
migration behavior, artifact locations used in testing, unresolved issues, and
the next ready task. Update this task's status and the task index without
rewriting earlier completion notes.
