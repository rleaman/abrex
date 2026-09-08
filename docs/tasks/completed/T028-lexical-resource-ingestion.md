# T028 completion: provenance-preserving lexical resource layer

Status: Complete for the streaming SQLite layer and bounded pilot scope.

## Delivered

- Added typed `FrequencyResourceConfig`, `ResourceVariant`,
  `ResourceSummary` and a narrow `ResourceQuery` protocol.
- Added a streaming gzip-JSON importer for the supplied `{SF: {LF: count}}`
  shape, using task-owned SQLite staging and atomic publication. Raw forms,
  normalized keys, count unit, source label and source hash are retained.
- Added identity and casefold normalization policies without forced LF
  collapse; repeated raw rows remain separate and aggregate-only resources
  return unknown document frequency.
- Added the bounded configuration example, resource-layer documentation and
  offline tests for streaming/chunk boundaries, collision preservation,
  repeatability and malformed inputs.

## Verification and evidence

The supplied file is 133,582,426 bytes with SHA-256
`eec42cb74577130f07cdd2422f664b21011e4fdd70847ffe5b5345f63c78f023`. The
bounded pilot imported only 64 rows into
`.artifacts/T028/frequency-pilot.sqlite`; all 64 happened to use the first
observed SF key `CNS`, with aggregate total count 120,393. SQLite retained the
same source fingerprint and `document_frequency=None`. The small report is
[T028-frequency-resource-pilot-report.json](../../artifacts/T028-frequency-resource-pilot-report.json).

The repository fast gate passed with 212 unit/contract tests. The full suite
passed 216 tests at 95.00% coverage; Ruff, formatting and strict mypy passed.

## Decisions and limitations

Count units remain `unknown` because the supplied extraction provenance does
not establish them. Aggregate counts are never presented as document counts,
corpus prevalence, gold labels or independent confirmation. Only the bounded
pilot was imported; no large-scale processing started. T046 owns external
dictionary discovery/acquisition, and T029/T034 own article-linked sampling
and scientific use.

Next ready tasks include T029 (sampling/leakage controls) and T046 after the
required T029/T034 ordering; T029 can now proceed because T026 and T027 are
complete.
