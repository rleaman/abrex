# T022 completion: real-data baseline smoke benchmarks

## Changed

- Added the deterministic `scripts/materialize_t022_smoke.py` selector and the
  checked-in selection manifest
  [`T022-smoke-selection.json`](../../configs/benchmarks/T022-smoke-selection.json).
  It selects 64 records from the audited T019 Ab3P corpus using
  `sha256(seed:record_id)`, restricted to records with non-empty gold, without
  inspecting resolver output.
- Added explicit Schwartz--Hearst, native-offset Ab3P, and fresh-build Ab3P
  experiment configurations under `configs/benchmarks/`.
- Fixed relative Ab3P installation roots to resolve to absolute executable and
  working-directory paths before subprocess execution, with a regression test.
- Added the compact tracked benchmark report
  [`T022-real-baseline-smoke-report.json`](../../artifacts/T022-real-baseline-smoke-report.json)
  and materializer coverage.

## Acceptance evidence

The fixed slice contains 64 documents and 143 exact-pair gold annotations. Both
baselines produced prediction artifacts covering all 64 documents exactly once
with zero resolver execution or mapping failures. No document failure was
converted to an empty successful prediction.

| Resolver | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Schwartz--Hearst | 110 | 5 | 33 | 0.9565 | 0.7692 | 0.8527 |
| Ab3P native offsets | 121 | 4 | 22 | 0.9680 | 0.8462 | 0.9030 |

These are bounded pilot measurements, not claims of superiority or corpus-wide
accuracy.

## Reproducibility and cache evidence

- Subset fingerprint:
  `e962059364d99004fa4f999914568f9451b275178446f5b8164d18a70cec371c`.
- Full T019 corpus fingerprint:
  `0e26c9ec4fcaf36721ddffdc9318e2f53c73f651fb24b46ce7e161520ef6d41d`.
- Schwartz--Hearst warm experiment replay reused the validated prediction
  cache; prediction fingerprint `e39deed4…94dd528` and evaluation fingerprint
  `8f31c158…6e733` were unchanged.
- Ab3P populated 64 raw cache entries. A direct raw-cache replay produced a
  byte-identical prediction artifact with fingerprint
  `840f3b618c0a997bd739b96c79f47d07b0f5b5bcb18bdc4fce5153caf3f262eb`.
- A second clean WSL build path produced the same Ab3P prediction and
  evaluation fingerprints (`840f3b…f262eb` and `31d23b…1b64d0`).
- The native-offset executable SHA-256 is
  `4a6b8c48dbb8e928c06464f94bf13295f524bd3c65e078c7d5169a131c431ee9`.
- Observed wall time was approximately 0.4 seconds for Schwartz--Hearst and
  101.6 seconds for the first native Ab3P experiment over 64 documents.

Full artifact paths, run manifests, commands, environment identities and
installation details are in the tracked report. Generated predictions, raw
cache entries and binaries remain under ignored `.artifacts/T022/`.

## Verification

- Focused T021/T022 regression tests: 16 passed.
- Unit/contract fast gate: 179 passed.
- Full suite and coverage gate: 183 passed, 95.01% coverage.
- Ruff format check: passed.
- Ruff lint: passed.
- Strict mypy: passed.
- `git diff --check`: passed.
- Live upstream Ab3P `make test`: passed on both task-owned builds.
- Live real-data cold and warm experiments: passed on the same audited slice.

## Scientific limitations and decisions

The smoke slice is deliberately hash-selected from the 546 non-empty-gold
records in the 1,237-record audited corpus; it is not a representative
estimate and excludes empty-gold documents by explicit operational choice.
Evaluation uses the T019 `exact_pair` contract and does not relax boundaries,
punctuation, overlap, or ambiguity semantics. The aggregate scores do not
resolve the source-license or benchmark-validity questions recorded by T019.
The comparison measures a native-offset Ab3P run and Schwartz--Hearst on one
historical corpus slice; it does not establish contemporary performance,
full-text coverage, or resolver superiority.

## Next ready tasks

The dependency graph now makes these independent tasks ready: T023 (PLODv2
span detection), T025 (bounded literature acquisition manifests), T028
(lexical resource ingestion), and T048 (BioADI runtime feasibility). T046
becomes ready after T028. Large-scale processing remains deferred.
