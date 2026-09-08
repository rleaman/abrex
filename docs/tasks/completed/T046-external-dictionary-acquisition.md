# T046 completion note: external dictionary acquisition

Status: Complete for the bounded ADAM and ALLIE acquisition/import pilots.
Source expansion, legal review and scientific use remain separate decisions.

## Delivered

- Added source-specific typed acquisition/import models and parsers for the
  official ALLIE REST XML format and ADAM tab-separated archive member in
  `src/abrex/resources/allie.py` and `src/abrex/resources/adam.py`.
- Added `resources acquire-allie` and `resources import-adam` CLI commands,
  YAML examples and focused format/retry/hash/query tests.
- Routed both normalized bounded artifacts through the T028 frequency SQLite
  resource interface. ALLIE pair IDs, variants and appearance counts remain in
  its manifest; ADAM preferred/morphological variants and long-form
  count/score fields are retained by the parser and the source archive remains
  immutable in ignored artifacts.
- Updated the source register/catalog with acquisition status, access terms,
  lineage and unresolved candidates. The two supplied Acromine publications
  remain one resource family; SaRAD, Stanford, ARGH and AcroMed remain
  unacquired discovery candidates.

## Real acquisition evidence

ALLIE’s official AML REST response was 53,889 bytes and yielded 16 bounded
pairs. Its T028 resource reports 16 variants, one short-form key and total
aggregate count 36,701 with `pair-appearance-count` semantics. ADAM’s official
3,645,440-byte tar and 2,508-byte README were acquired. The local parser
scanned 57,827 valid rows with zero malformed rows and imported the first 64
into T028, reporting 54 short-form keys, 66 variants and total count 1,966
under `definition-count` semantics.

Hashes, URLs, raw/normalized artifact paths, source lineage and the ADAM count
discrepancy are recorded in
[T046-external-dictionary-pilot-report.json](../../artifacts/T046-external-dictionary-pilot-report.json).
Raw bytes and SQLite outputs remain ignored under `.artifacts/T046/`.

## Verification

- Focused T046 tests: 22 passed (8 ALLIE, 14 ADAM).
- Live ALLIE acquisition and direct T028 variant lookup passed;
  `document_frequency` remained unknown.
- Live ADAM bounded import and direct T028 lookup passed.
- Mocked parser, retry/failure, malformed-row and configuration cases passed.
- Repository fast gate: 247 passed. Full suite: 251 passed, 95.02% coverage.
  Ruff format/check, strict mypy and `git diff --check` passed.

## Open decisions and limitations

- ADAM’s README says 59,405 distinct pairs but the archive yielded 57,827
  valid tabular rows. Determine whether this is a row-vs-pair definition or a
  source-version discrepancy before full import.
- ADAM’s non-commercial/no-redistribution language and GPL reference require
  legal review; do not redistribute the acquired archive or derived bulk
  artifact.
- ALLIE’s extraction lineage is ALICE-derived, so it is not independent
  confirmation. Its bulk archive and terms were not expanded in this pilot.
- Acromine REST access and all remaining dictionary candidates are pending;
  no unverified mirror was substituted.
- T034 must decide how, or whether, these resources become lexical evidence;
  dictionary membership alone is not a local definition assertion.

## Next ready tasks

T030 is ready for the auditable contemporary annotation pilot. T047 is ready
to finalize large-scale corpus selection from T029 exclusions. T048 remains an
independent BioADI feasibility branch after T022.
