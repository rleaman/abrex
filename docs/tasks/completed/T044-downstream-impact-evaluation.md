# T044 completion: downstream impact evaluation

## Delivered

- Added the typed `DownstreamAdapter` contract for unchanged article text plus
  explicit `MentionLink` inputs.
- Added traceable `DownstreamEntity` values and
  `DownstreamImpactResult` comparison metrics for introduced/removed entities,
  precision, recall and false expansions.
- Added no-gold behavior that leaves quality metrics unclaimed, regression
  fixtures, and the tracked contract report at
  `docs/artifacts/T044-downstream-impact-report.json`.

## Verification

- Frozen-input comparison fixture with introduced/removed and false-expansion
  accounting: 2 tests passed.
- Repository unit/contract fast gate: run before commit.
- Ruff, strict mypy and diff checks: passed.

## Limitation and blocker

No user downstream pipeline interface, permitted frozen downstream dataset, or
approved success metric is present in the repository. Per T044 acceptance, the
adapter contract and fixtures are complete but real impact validation remains
incomplete. No deployment recommendation or biological improvement claim is
made.

## Next ready task

T045 can package the validated software and clearly label T042/T044 research
artifacts as pending or incomplete; publication and external release remain
out of scope.
