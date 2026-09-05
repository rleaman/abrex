# T008 completion note

## Changed

- Added a six-document, human-readable regression corpus covering standard and
  reverse parenthetical order, nested parentheses, hyphenated/digit forms,
  multiple definitions, a boundary-sensitive long form, a false-positive
  parenthetical, and Unicode biomedical text.
- Added reviewed Ab3P raw output and deterministic `predictions-v1` golden
  artifacts, including an explicit empty prediction record where Ab3P finds
  no pair.
- Added a regression suite that checks canonical record semantics, Ab3P
  parsing and span reconstruction, and exact pair outcomes/metrics.

## Verification

- `env313\\Scripts\\python.exe -m pytest tests/regression`
- Full repository quality gate run after the T008 tests passed.

## Unresolved issues

Ab3P behavior for reverse-order definitions remains represented by the reviewed
empty baseline output; no new scientific matching or boundary policy was
introduced.
