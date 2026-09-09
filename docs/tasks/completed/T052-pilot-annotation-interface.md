# T052 pilot annotation interface

Status: Partial delivery; the local reviewer and interchange are available,
with explicit method-availability diagnostics and browser automation still
unavailable in this environment.

The corrected packet was built from the v2 manifest with:

```powershell
$env:PYTHONPATH = "src;env313/Lib/site-packages"
py -3.13 scripts/build_t052_packet.py .artifacts/T051/random-pilot-v2/pilot-manifest.json .artifacts/T052/review-packet-v2.json --bioc .artifacts/T052/review-packet-v2.bioc.xml
py -3.13 scripts/run_t052_reviewer.py .artifacts/T052/review-packet-v2.json --port 8765
```

The corrected packet contains 60 traceable cases, balanced 30/30 source-arm
diagnostics, a four-case article cap, structural metadata where available,
explicit shortages for all strict comparison strata, JSON save/resume state and
BioC XML interchange. 40 cases contain assisted Schwartz–Hearst suggestions;
all cases retain method diagnostics and are explicitly labeled diagnostic, not
agreement/disagreement or no-definition gold. HTTP smoke testing confirmed the
page, packet, save/reload persistence and `/api/bioc` endpoint. The UI exposes
accept/reject/uncertain/no-definition decisions, exact half-open span edits,
notes, navigation, filtering, source structures, JSON backup and BioC
download. Suggestions are assisted and are not independent gold.

Tracked summary: [T052-review-pilot-summary.json](../../artifacts/T052-review-pilot-summary.json). Corrected packet SHA-256 is `c7a6e431cabf0dc74b62e67b5b83dd3912d1525a6798fdc4bded8bc5cb8a088c`; TeamTat import/export fidelity was not independently tested.
