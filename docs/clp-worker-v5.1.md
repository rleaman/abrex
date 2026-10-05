# Pinned full CLP V5.1 worker

The full CLP implementation is preserved as
`resources/clp/clp-v5.1-source.zip` from CellLiteraturePipeline commit
`323fd4f51aa3c5b54ed30f37dd297b00b49e277e`. Its SHA-256 is
`290a52ad53216de64fca78abff2682057cc77b0d3c3ee698580a8ca9f94df7d7`.
It is not the `clp_table_v5_1` two-column comparator.

`scripts/run_clp_worker_v2.py` executes the archive through a versioned JSON
boundary that retains passage order, source passage indexes, section/type
infons, table XML, dispositions, orientation, rules, and exact occurrence
spans. It fixes the policy threshold at `0.52`. Cached historical requests use
the original `jev-latest` request identity, while every saved response is
identified as `jev-1.13.0`; no new live request is made by this worker.

Run the tested deterministic smoke from the Abrex repository root with the
CellLiteraturePipeline Python environment and dictionary:

```powershell
..\CellLiteraturePipeline\env313\Scripts\python.exe scripts\run_clp_worker_v2.py `
  --request tests\fixtures\clp_worker_v2_request.json `
  --response evidence\campaign-2026-10\milestone-a\clp-worker-v2-smoke-response.json `
  --dictionary ..\CellLiteraturePipeline\resources\abbreviations\abbr_frequency_2024.json.gz `
  --mode rules-only
```

Expected output begins with `{"documents": 1, "mode": "rules-only"}`. The
response must contain one `PATTERN_1:ALTERNATING` pair at short span `[14,17)`
and long span `[18,36)`. The V2 mapper validates these spans against the exact
request text before creating Abrex candidates.

For a saved full replay, add `--mode cached-full --jev-cache <cache.jsonl>`.
Use the verified direct versions in
`docs/artifacts/clp-worker-v5.1-requirements.txt`. A future fresh scientific
run must separately authorize its model destination and monetary/request cap.
