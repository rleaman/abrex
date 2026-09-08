# T025 completion: bounded literature acquisition manifests

Status: Complete for the bounded acquisition engineering and live pilot scope.

## Delivered

- Added typed `LiteratureAcquisitionConfig`, fixed-ID batching, request
  fingerprinting, retry/backoff, rate limiting, atomic `.part` writes, reuse
  after hash verification, missing/failed/partial accounting, dry-run
  estimates and offline manifest replay in
  `src/abrex/literature/acquisition.py`.
- Added `literature acquire` and `literature replay` CLI commands.
- Added the two-ID example at
  `configs/literature/T025-pubmed-pilot.yaml` and documented the raw/source
  boundary in `docs/literature-integration.md`.
- Added offline tests for configuration validation, bounded estimates,
  retry/reuse, missing responses, path safety and hash validation in
  `tests/unit/test_literature_acquisition.py`.

## Verification and evidence

The dry run estimated 2 IDs, 1 request and 200,000 bytes. The authorized live
pilot used one NCBI EFetch request for PMIDs `12603049` and `29446729`; it
downloaded one 12,980-byte XML response with SHA-256
`0734a0d3a1680cd121dfd1bcbdc0cec81d8ed645d95603b34b9d91316fad8ac8`.
A rerun reused the unchanged response. Offline replay checked one successful
entry and returned `valid=1`, `invalid=[]`. The detailed small metadata report
is [T025-pubmed-pilot-report.json](../../artifacts/T025-pubmed-pilot-report.json);
raw bytes remain under ignored `.artifacts/T025/`.

Focused checks passed: 5 acquisition tests, 14 existing literature tests,
Ruff, formatting and strict mypy. The repository fast gate and milestone
coverage gate are recorded in the milestone review after the remaining
independent ready tasks are handled.

## Decisions and limitations

The connector pins a fixed returned-ID list rather than issuing a mutable
search. It records access metadata without asserting that every fetched
article is redistributable. API keys are read only from an environment
variable and are not written to manifests. T025 does not parse XML, select a
scientific population, or begin bulk retrieval; those decisions remain for
T026/T029/T047.

Next dependency-ready task: T026, local PubMed/BioC parsing.
