# T062 development recovery evidence

This directory contains the immutable, occurrence-level inputs behind the T062
readout:

- `development-ledger-v1.json` merges the frozen T057 relations with eight new
  strict relations accepted during T061. Existing T057 dispositions are never
  reclassified by the supplement.
- `recovery-table-v1.jsonl` records, for each of 67 strict and 12 diagnostic
  relations, whether each method produced the exact pair, overlapping wrong
  boundaries, both independent PLOD endpoints without the correct pairing, or
  no candidate.
- `prediction-dispositions-v1.jsonl` accounts for all 165 method predictions,
  separating strict true positives, explicit outside-target matches, and false
  positives or duplicates.

These are assisted development artifacts. They are not independent gold,
population estimates, or evidence of fresh-sample superiority. Rebuild them
and the linked reports with:

```powershell
.\env313\Scripts\python.exe scripts\build_t062_readout.py
```

The concise readout is
[`docs/artifacts/T062-development-readout.md`](../../docs/artifacts/T062-development-readout.md).
