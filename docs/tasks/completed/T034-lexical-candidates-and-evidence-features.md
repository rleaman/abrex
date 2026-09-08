# T034 completion: lexical candidates and evidence features

## Delivered

- Added the registry-backed `lexical_resource` generator with typed local
  window bounds. It emits a pair only when exact short- and long-form spans
  both occur in the same canonical document.
- Preserved raw variants, normalization collisions, source labels and
  resource SHA-256 values in candidate provenance. Added content-aware cache
  identities for lexical candidates and features.
- Added `lexical_resource_evidence`, a separate feature extractor reporting
  observed aggregate counts, source agreement, ambiguity, exact local pair
  support and bounded contextual support. It does not use gold or structural
  construction labels.
- Added a typed example at
  `configs/benchmarks/T034-lexical-evidence.yaml`.

## Evidence

The reproducible pilot is
[`T034-lexical-evidence-ablation.json`](../../artifacts/T034-lexical-evidence-ablation.json).
On the same 64-record T022 smoke universe (fingerprint
`e962059364d99004fa4f999914568f9451b275178446f5b8164d18a70cec371c`) and the
bounded T028 aggregate pilot, lexical candidates added 6 candidates (1,581 vs
1,575), changed exploratory candidate precision by -0.000296, and did not
change candidate recall (123/143, 0.86014). This is a bounded no-gain result,
not evidence that lexical resources are ineffective at work scale.

## Leakage and limitations

T029's article-level separation remains the governing resource-building
control; this report uses the existing aggregate T028 pilot, whose document
overlap is unknown and whose document frequency is explicitly absent. No
evaluation/challenge article is used to build a new resource view here. A
future article-linked resource must be built only from `lexicon_allowed`
records and frozen before held-out evaluation. No global disambiguation or
blind terminology authority was added.

## Verification

- Focused lexical/structural tests: 6 passed.
- Targeted strict mypy on changed Python files: passed.
- Ruff check and format: passed.
- Bounded ablation report generation: passed.
- Repository unit/contract fast gate: run as part of task handoff.

## Next ready task

T035 is ready: weak-evidence ledger and silver-label materialization can now
consume the explicit lexical and hybrid evidence without treating either as
gold.
