# Milestone C Linux result

Status: **returned, imported, and validated**

The replacement prediction-only bundle completed on the fresh Linux server and
the returned archive was imported on October 7, 2026. The archive has seven
members, passes ZIP integrity validation, contains no gold or review state, and
is bound to bundle
`a1d57ed9ee18e1fc88ebe85e01ae33dddf3c3b853f32065b0ccf778dba1777be`.
Its SHA-256 is
`740c02ac01f8a40165a636a0b011feafd36922a6230a5bfa3bf82539a560b565`.

Both jobs completed against all 120 frozen prediction-only documents:

- Ab3P v3 returned 47 exact-grounded predictions in 23 documents. One document,
  `milestone-c-60282f673febc655719c`, has the preserved
  `RESOLVER_EXECUTION_FAILED` diagnostic. Ab3P reported the short form `WT` at
  byte/character interval `[129, 131)`, where the source slice is `kl`. The
  mapper did not search, guess, or convert this failure into an empty prediction.
- PLODv2 pairing returned 93 exact-grounded predictions in 54 documents, with no
  resolver failures or diagnostics.

The imported prediction SHA-256 values are respectively
`39beb4ec660f3d83ff63033927201592309733b782b12dacf8dd0019b6db665b` and
`ccaadc122023fc1bd37ebbdd88ffcd6a80a26b38992c4f5c2ea101eb3b34daac`.
The complete machine-readable validation and environment record is
`evidence/campaign-2026-10/milestone-c/linux-execution-receipt-v1.json` and can
be rebuilt with `scripts/build_milestone_c_linux_receipt.py`.

No prediction was compared with gold during import or validation. Confirmatory
scoring remains withheld until the independent second review and any resulting
adjudication are immutably locked. No further Linux action is required.
