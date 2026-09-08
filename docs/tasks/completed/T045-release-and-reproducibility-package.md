# T045 completion: local release and reproducibility package

## Delivered

- Built the `abrex-0.1.0-py3-none-any.whl` local release candidate (231,082
  bytes; SHA-256
  `f14dedc84154ffb8661205cc2f323a85ef9bc6497013e5e49b3fbf411e8f3268`).
- Reinstalled the explicit wheel with no dependencies and verified package
  import plus offline CLI configuration resolution.
- Added [`docs/release-candidate.md`](../../release-candidate.md) with
  installation, embedding/runtime and non-redistribution guidance.
- Added [`T045-release-manifest.json`](../../artifacts/T045-release-manifest.json)
  recording package identity, quality evidence, research artifact references,
  notices and unsupported claims.

## Verification

- Wheel build: passed after installing the declared Hatchling build backend.
- Explicit-wheel reinstall: passed.
- Offline import and CLI smoke: passed.
- Repository unit/contract gate: 307 passed.
- Ruff, strict targeted mypy and diff checks: passed.

## Research limitations

This is a local release candidate, not a published package or completed
research release. T042 lacks an approved work-scale source snapshot,
permissions and measured cost envelope. T044 has only its adapter contract and
fixtures because the user's downstream pipeline and dataset are unavailable.
T040 therefore retains native-offset Ab3P as an exploratory candidate without
supporting a production-improvement claim.

## Next action requiring external input

To complete T042/T044 research validation, provide or approve the concrete
literature snapshot and reuse terms, measured T041 work-scale budget, and the
downstream pipeline interface plus frozen evaluation data/metric. No upload or
publication was attempted.
