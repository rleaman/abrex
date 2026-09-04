# Canonical Corpus Artifacts

T004 canonical artifacts are UTF-8 JSONL files with one versioned
`canonical-v1` record per line. Records are immutable domain values serialized
with stable JSON key ordering and deterministic record ordering. Duplicate
records are retained; no evaluation duplicate policy is introduced here.

Each JSONL artifact has a sibling `*.manifest.json` file. The manifest records
the canonical data SHA-256 fingerprint, record and annotation counts, adapter
and normalizer identities, optional resolved-configuration and source-byte
fingerprints, and the structured validation summary. Filesystem paths are not
part of the canonical data fingerprint.

Build an artifact from a corpus YAML configuration with:

```console
python -m abrex corpus build docs/examples/corpus-fixture.yaml \
  --output data/processed/fixture.jsonl
```

Use `read_canonical_dataset` when both files must be loaded and their
fingerprint and counts checked. Use `CanonicalValidator` directly when a
caller needs a permissive result containing retained records plus its issue
summary. Strict mode raises `CanonicalValidationError` after collecting all
issues with error severity; permissive mode retains valid records and reports
dropped rows.

Incomplete spans are reported as `unscoreable`, and overlapping annotation
spans are reported as `ambiguous`. These are audit classifications only;
matching and scoreability policies belong to the evaluator.
