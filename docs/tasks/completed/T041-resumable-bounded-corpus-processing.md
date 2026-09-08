# T041 completion note

## Changed

- Added typed `ShardedProcessingConfig`, `DocumentProcessor`,
  `ShardedRunResult`, deterministic `shard_for_document`, and `run_sharded` in
  `src/abrex/experiments/sharded.py`.
- Added disk-backed routing and per-shard streaming processing so the input
  document collection is never materialized in memory. Output rows preserve
  document IDs and input content fingerprints.
- Added atomic output publication, complete-manifest-last semantics, stale
  `.part` cleanup on resume, identity-protected reuse, retry limits, failure
  quarantine, and throughput/output-byte measurements.
- Added public documentation in `docs/sharded-processing.md` and exports from
  `abrex.experiments`.

## Verification

- Focused T041 tests: 4 passed with elevated filesystem access. They cover
  idempotent reuse, deterministic input identity, retry/quarantine accounting,
  interrupted publication and resume.
- Ruff format/check and strict mypy passed for the implementation and tests.
- The repository fast gate will be run after this task's documentation and
  export changes; the known OneDrive pytest temporary-directory restriction is
  retried with elevated access.

## Scientific and operational limits

This is a bounded orchestration substrate, not a distributed framework. It
does not select a production corpus, invent document splits, or claim a
work-scale throughput or peak-memory result. `peak_memory_bytes` is explicitly
recorded as unavailable until a measured deployment supplies it. Failed and
unprocessed documents remain visible in the manifest and quarantine artifacts.

## Next ready tasks

T031 remains in progress pending its real three-resolver matrix. T042 remains
gated by T040, T047 and campaign decisions.
