# T008 completion note

## Changed

- Added a six-document, human-readable regression corpus covering standard and
  reverse parenthetical order, nested parentheses, hyphenated/digit forms,
  multiple definitions, a boundary-sensitive long form, a false-positive
  parenthetical, and Unicode biomedical text.
- Added explicitly identified curated Ab3P-shaped raw output and deterministic
  `predictions-v1` golden artifacts, including an explicit empty prediction
  record for the reverse-order case.
- Added `ab3p_outputs.provenance.json`. It records that these are synthetic
  parser/reconstruction fixtures because no Linux Ab3P executable was
  available; it does not misrepresent them as a live scientific baseline.
- Added a regression suite that checks canonical record semantics, Ab3P
  parsing and span reconstruction, and exact pair outcomes/metrics.

## Verification

- `env313\\Scripts\\python.exe -m pytest tests/regression`
- Full repository quality gate run after the T008 tests passed.

## Unresolved issues

Before using this fixture as a scientific Ab3P performance baseline, regenerate
`ab3p_outputs.json` with the intended Linux executable and fill in its resolved
path, SHA-256, installation identity, and UTC generation timestamp. The
regression fixture remains useful for parser and span-reconstruction tests in
the meantime.
