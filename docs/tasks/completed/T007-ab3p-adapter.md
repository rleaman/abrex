# T007 completion note

## Changed

- Added the registry-backed `ab3p` resolver with `cache_only`, `subprocess`,
  and `cache_then_subprocess` backends.
- Added independently testable deterministic input construction, parsing of
  the original `sf|lf|precision` output, and explicit canonical span
  reconstruction ambiguity/failure handling.
- Added portable JSON cache entries containing raw input/output, execution
  status, document/content identity, configuration identity, and provenance.
- Added safe argument-vector subprocess execution with timeout and temporary
  file cleanup, without adding Ab3P as a Python dependency.
- Documented Linux cache population and Windows/offline replay configuration.

## Verification

- Repository quality gate: `env313\\Scripts\\python.exe -m ruff format --check
  src tests`, `ruff check`, `mypy`, and `pytest tests/unit tests/contract`.
- No real Linux Ab3P executable was available during development; live tests
  are explicitly optional and mocked/unit tested.

## Scientific/platform notes

Cache identity uses canonical document ID/content and exact input fingerprints,
adapter/cache version, backend, and installation label; absolute executable
paths are not identity inputs. Provenance records configured executable,
optional installation label, executable SHA-256 when readable, platform, and
creation time. Repeated surface forms with more than one valid long/short
placement are reported as ambiguous rather than assigned arbitrarily. Native
Windows execution remains intentionally unsupported; cache replay has no such
dependency.
