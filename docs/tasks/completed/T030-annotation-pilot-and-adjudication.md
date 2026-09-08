# T030 completion note: auditable contemporary annotation pilot

Status: Complete for the versioned annotation workflow and bounded local pilot.
Independent review and scientific gold certification remain pending.

## Delivered

- Added typed annotation-packet models and validation in
  `src/abrex/corpora/annotation_pilot.py`.
- Added canonical JSONL conversion that preserves source text, half-open spans,
  relation IDs, origin, status, revision and adjudication history.
- Added deterministic difficult-case review-packet selection and explicit
  assisted/independent/unresolved accounting.
- Added the `abrex annotations run` CLI command, YAML configuration, compact
  fixture and operational [annotation guidelines](../../annotation-guidelines.md).

## Evidence and artifacts

The bounded four-case pilot contains two independent labels, one assisted label,
one unresolved difficult evaluation case, one empty-definition case and a
two-case review packet covering table/caption/ambiguous phenomena. The canonical
artifact fingerprint is `71cc0fb84e84d6a0f509595b5859f4efc367e5ad8595370ee47989b1c2d3df20`.
The full evidence record is
[T030-annotation-pilot-report.json](../../artifacts/T030-annotation-pilot-report.json).
Generated packet files remain ignored under `.artifacts/T030/`.

## Verification

- Focused suite: `5 passed`.
- Round-trip, canonical import, invalid-offset rejection, adjudication history
  and deterministic review selection are covered.
- The pilot explicitly reports `claims_allowed: false` and
  `provisional_silver_pending_independent_review`.
- Repository-wide fast gate: `252 passed`; full gate: `256 passed`, total
  coverage `95.01%`; ruff format/check, mypy and `git diff --check` pass.

## Limitations and next decisions

This is an engineering and workflow pilot, not a contemporary accuracy result.
Reviewers, independent-pass count, adjudication policy and the final unresolved
scoreability policy must be chosen before evaluation gold is certified. The
provisional evaluation packet must remain isolated from T031 development and
T037 training.

## Next ready task

T047 is ready to formalize the large-scale corpus selection proposal after T025
and T029. T023 remains a separate runtime/integration blocker for the PLODv2
branch.
