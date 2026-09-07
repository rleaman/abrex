# T020 Ab3P runtime and cache identity

## Implemented scope

- Added typed `Ab3PInstallationConfig` settings for the T018 installation
  manifest, installation root, executable, and WordData directory.
- Verified manifest-declared executable and semantic-resource SHA-256 values
  before live execution. The installation root is passed as subprocess `cwd`,
  so Ab3P resolves `path_Ab3P` without process-wide `chdir` or shell parsing.
- Added resolver-owned identity containing manifest, executable, resource,
  adapter, and wrapper versions. The identity is included in raw cache keys,
  raw cache provenance, and experiment prediction cache keys/run manifests.
- Versioned raw entries as `ab3p-cache-v3`. Legacy `ab3p-cache-v2`
  label-only entries are rejected explicitly. Cache-only replay validates the
  portable manifest identity without requiring a local Linux executable.
- Retained an explicit digest-only compatibility mode, marked with
  `resource_sha256: unverified`; installation manifests are required for
  verified executable/resource identity.

## Files changed

- `src/abrex/resolvers/adapters/ab3p.py`
- `src/abrex/resolvers/adapters/ab3p_resolver.py`
- `src/abrex/infrastructure/ab3p.py`
- resolver package exports and `docs/examples/resolver-ab3p-cache.yaml`
- `docs/resolvers.md`
- `tests/unit/test_ab3p.py`

## Verification

Focused checks:

```text
13 passed in 1.77s
Ruff format check: passed
Ruff lint: passed
mypy: passed, 109 source files
```

The new regression fixture verifies cache round-trip across live/cache-only
configuration, rejection after WordData mutation, and subprocess `cwd` set to
the installation root. The existing T018 artifact remains the real verified
installation manifest:
`docs/artifacts/ab3p-installation-manifest.json`, SHA-256
`0b7d5a83d667e65c0714ab11b5e38392aa7ae2c60e71333892967919e22ccb31`.

An attempted ABREX-on-WSL smoke could not start because the available WSL
Python does not have `pydantic` installed. T018 independently records the
real executable's successful unrelated-working-directory smoke. A direct
ABREX live smoke with the new Python boundary remains operational validation
pending, not a fixture-based success claim.

## Open decisions and next task

Digest-only compatibility remains intentionally available for callers that
cannot yet provide a T018 manifest, but it does not establish resource
identity and should not be used for a verified benchmark run. Native Windows
Ab3P execution remains unsupported; Windows uses portable `cache_only`
replay. T021, the native-offset adapter, is the next ready task after the
pending WSL runtime smoke is supplied.
