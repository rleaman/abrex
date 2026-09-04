# T011 completion note

## Changed

- Added offline, registry-backed adapters for BioC XML/JSON sources, SDU
  acronym-identification JSON, and tab-separated corrected pair sources.
- Registered explicit variants for Schwartz & Hearst, its BADREX correction,
  Ab3P, BIOADI, MEDSTRACT, corrected MEDSTRACT, and SDU@AAAI-21/22.
- Preserved source coordinates/text and adapter variant identity in canonical
  provenance; reconstructed SDU offsets and pair-only document text are
  explicitly recorded as transformations.
- Added synthetic structural fixtures and adapter-specific tests, and
  documented source formats, offline/licensing expectations, and reconstruction
  choices.

## Verification

- Ruff format check: passed.
- Ruff lint: passed.
- mypy: passed (`55` source files).
- Unit/contract gate: passed (`88 passed`) with elevated filesystem access.
- Coverage run: `88 passed`, but repository coverage was `96.73%` and did not
  meet the configured 100% threshold because the new historical parser's
  defensive/error branches are not yet exhaustively covered.

## Unresolved issues

Real corpus downloads, licensing decisions, and dataset-specific source
quirks remain user-supplied and were not committed. Coverage follow-up should
add tests for malformed BioC/SDU/pair inputs and all parser branches before
claiming the repository-wide coverage gate is fully green.
