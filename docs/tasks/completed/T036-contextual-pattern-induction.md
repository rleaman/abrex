# T036 completion: contextual pattern induction

## Delivered

- Added typed `PatternInductionConfig` with bounded context, support and
  template-size limits.
- Added `ContextTemplate` with `<SF>`/`<LF>` placeholders, normalized local
  context, explicit direction and safe matching. No arbitrary generated code
  or unrestricted user regex is executed.
- Added `induce_patterns` to group positive T035 evidence by generalized
  context, count distinct documents and span pairs, retain evidence IDs, and
  mark support-insufficient proposals rejected rather than promoting them.
- Added held-out `validate_pattern` accounting for positive matches and misses.

## Verification

- Synthetic reverse-order known-pattern recovery: passed.
- Distinct-document/pair promotion and held-out matching: passed.
- Focused tests: 1 passed.
- Repository unit/contract fast gate: 298 passed.
- Ruff, strict mypy and diff checks: passed.

## Scientific limitations

The repository has no approved multi-document reviewed T035 evidence corpus
large enough to claim generalization or precision. The implementation is
ready for a discovery/development split, but no rule is promoted from
self-generated support alone. Literal pair strings remain masked in templates;
source-family and article-level leakage controls remain required at artifact
construction time.

## Next ready task

T037 is ready to materialize leakage-safe candidate training datasets from
explicit gold/silver labels and pattern/evidence lineage.
