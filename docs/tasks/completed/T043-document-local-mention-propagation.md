# T043 completion: document-local mention propagation

## Delivered

- Added typed `MentionLinkConfig` and immutable `MentionLink` results.
- Added deterministic `link_mentions` with article/section scope, nearest
  preceding or nearest-any ordering, case/plural options, conflict abstention,
  exact mention spans and explicit undefined outcomes.
- Added `ArticleResolutionService.resolve_and_link_mentions` so a configured
  resolver's definitions flow into the downstream linker without changing
  resolver or evaluation contracts.
- Preserved source article/section IDs and separated definition detection from
  mention-linking evidence and statuses.

## Verification

- Nearest-preceding, before-definition/undefined, and section-redefinition
  tests: 2 passed.
- Targeted strict mypy and Ruff: passed.
- Repository unit/contract fast gate: run before commit.

## Scientific limitations

The selected scope and conflict policies remain explicit downstream choices;
no global sense disambiguation or entity normalization is performed. The
fixtures do not establish production linking accuracy.

## Next ready task

T044 is ready to evaluate downstream impact using these inspectable mention
links while keeping definition and propagation metrics separate.
