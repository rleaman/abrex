# T067 frozen fresh-check inputs

These files were materialized only after the corrected prediction-blind T066
lock was verified.

- `fresh-prediction-input-v1.jsonl` contains the 32 source documents and zero
  gold annotations. It is the only corpus used to prepare resolver jobs.
- `fresh-strict-gold-v1.jsonl` contains 32 strict exact-pair relations and is
  local evaluation evidence. It must never enter a portable bundle.
- `fresh-eligibility-ledger-v1.json` preserves all 40 reviewed relations: 32
  strict and 8 diagnostic, with no unresolved relations.
- `fresh-run-manifest-v1.json` binds the packet, corrected lock, T063 protocol,
  frozen component configurations, article isolation, and both dataset
  fingerprints.

The execution bundle and exact copy/run/copy-back procedure are documented in
[`docs/T067-linux-runbook.md`](../../docs/T067-linux-runbook.md). The
checksummed Linux results were returned and imported on October 5, 2026. The
frozen [primary readout](../../docs/T067-fresh-evaluation-readout.md) and its
[machine-readable report](../../docs/artifacts/T067-fresh-evaluation-readout-v1.json)
are now present. The exact-union challenger failed the predeclared
false-positive tolerance; no post-reveal tuning was performed.
