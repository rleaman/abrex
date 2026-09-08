# T021 completion: native Ab3P offset adapter

## Changed

- Added a versioned `identify_abbr_offsets` frontend around the unchanged
  upstream Ab3P library. It emits JSONL with the detected pair, precision,
  strategy, line identity, line byte origin/length, and native `sf_offset` /
  `lf_offset` byte offsets.
- Added strict parsing and UTF-8 byte-to-Python-character mapping for exact
  canonical spans. Mapping rejects stale line origins, out-of-range offsets,
  non-boundary UTF-8 coordinates, and reported-form/surface-text mismatches.
- Kept text-only reconstruction as a separate legacy path with explicit
  ambiguity errors. Output format and wrapper/parser identities participate in
  cache identity.
- Added the offset configuration example, resolver documentation, focused
  unit/regression coverage, and build-manifest support for the wrapper.

## Live conformance evidence

Command (inside the documented Ubuntu WSL Python environment):

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/mail/Documents/Projects/abrex && "$HOME/.local/share/abrex/venv313/bin/python" scripts/build_ab3p.py --ab3p-source ../Ab3P --ncbi-source ../NCBITextLib --output .artifacts/T021/live-build --manifest .artifacts/T021/live-installation-manifest.json'
```

The task-owned build completed successfully. Unchanged upstream Ab3P and the
offset frontend both processed the same three-line Unicode/multiline pilot;
each emitted two detections (`TNF` and `IL-6`) with matching pair text and
precision. The offset records mapped to exact source slices. The pilot also
included a non-ASCII prefix and the build's line identity/byte-length checks;
the unit suite covers repeated definitions, later reuse, CRLF, Greek text and
UTF-8 boundary failures.

The unchanged upstream `make test` passed. The generated installation
manifest is `.artifacts/T021/live-installation-manifest.json`; the native
frontend SHA-256 is
`4a6b8c48dbb8e928c06464f94bf13295f524bd3c65e078c7d5169a131c431ee9`.
Generated binaries and verification output remain under ignored
`.artifacts/T021/`.

## Verification

- `env313\Scripts\python.exe -m pytest tests\unit\test_ab3p.py -q --basetemp .pytest-tmp\T021-focused`: 14 passed.
- Native WSL build and live offset pilot: passed; two offset records and two
  unchanged-upstream detections.
- Upstream Ab3P `make test`: passed.

The repository fast quality gate and full coverage gate are still required at
the T022 milestone boundary and will include this implementation.

## Scientific limitations and decisions

Native offsets are treated as UTF-8 byte offsets into each exact input line;
the adapter does not normalize text or select a nearest occurrence. The
frontend preserves upstream detection behavior and only adds coordinates.
Image-only text, benchmark quality and baseline accuracy remain outside T021.
The existing T018 installation manifest is extended by the task-owned live
manifest to identify the wrapper executable; cache consumers must use the
matching manifest identity.

## Next ready task

T022: run reproducible real-data baseline smoke benchmarks on the audited
Ab3P corpus, comparing Schwartz--Hearst and real Ab3P without changing gold
semantics.
