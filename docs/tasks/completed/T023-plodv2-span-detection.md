# T023 completion note

## Changed

- Added typed `PlodConfig`, injectable `PlodTagger`, `PlodSpanDetector`, raw /
  validated span records, and deterministic span serialization in
  `src/abrex/resolvers/plod.py`.
- Registered the optional `plodv2` resolver. Flair and PyTorch are imported
  only when the component is constructed; core imports remain dependency-free.
- Mapped PLOD's `AC` label explicitly to `SF`, retained `LF` independently,
  preserved model scores and checkpoint/config fingerprints, validated every
  translated span against canonical text, and retained window provenance and
  diagnostics.
- Added bounded character windows with explicit overlap and duplicate policy;
  no pairing or pair-probability interpretation is performed.
- Documented YAML configuration and the independent-span contract in
  `docs/resolvers.md`.

## Verification

- `env313\Scripts\python.exe -m pytest tests/unit/test_plod.py -q` — passed,
  5 tests.
- Ruff format/check and strict mypy for the changed implementation and tests —
  passed.
- `scripts/quality_gate.py` — formatting, lint and mypy passed; pytest reached
  148 passed but encountered the documented OneDrive temporary-directory
  permission failures (126 setup errors and one existing Ab3P temp-dependent
  failure). A fresh accessible temporary directory was not available in this
  shell.
- The documented `wsl.exe -d Ubuntu` real-checkpoint command could not run:
  this host exposes the Microsoft Store WSL stub/help output rather than the
  installed Ubuntu distribution. The supplied runtime smoke remains prior
  standalone live/offline evidence; this note does not claim a new run.

## Artifacts and limitations

The checkpoint remains outside Git at the path and SHA-256 recorded in
[`docs/plod-runtime.md`](../../plod-runtime.md). Span artifacts contain raw
labels, canonical offsets, scores, window origins and diagnostics, but the
resolver output is intentionally unpaired. PLOD span quality is not a claim
about pair accuracy. T024 is now ready.
