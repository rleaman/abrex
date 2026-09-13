# T054 audit supplement schema

The audit supplement is an additive `t054-audit-supplement-v1` JSON document.
It links to the immutable T052 packet identity, the byte hash of the T052
annotation state, and the T053 audit-packet hash. The supplement does not alter
the T052 packet or its annotation state. Existing T052 JSON and BioC files are
still read and exported by their existing interfaces.

All offsets are half-open Unicode code-point intervals into each case's
`canonical_text`. `evidence_spans` is ordered and may contain multiple
fragments. `reconstructed_expansion` has the explicit `reconstructed` label
and intentionally has no source coordinates.

The following abbreviated examples show the intended distinctions:

```json
{
  "relation_id": "r-expansion",
  "support": "supported",
  "relation_kind": "abbreviation_expansion",
  "evidence_structure": "contiguous_shared",
  "context_requirement": "text_alone",
  "scope": "body_text",
  "anchor_spans": [{"start": 23, "end": 26, "text": "TNF"}],
  "evidence_spans": [{"start": 0, "end": 21, "text": "Tumor necrosis factor"}]
}
```

For discontinuous evidence, retain every exact fragment in order:

```json
{
  "relation_id": "r-discontinuous",
  "support": "uncertain",
  "relation_kind": "abbreviation_expansion",
  "evidence_structure": "discontinuous",
  "context_requirement": "document_structure",
  "scope": "table",
  "anchor_spans": [{"start": 42, "end": 45, "text": "ABC"}],
  "evidence_spans": [
    {"start": 0, "end": 8, "text": "Alpha "},
    {"start": 20, "end": 31, "text": "beta complex"}
  ]
}
```

An unsupported pair remains explicit, and a source-error proposal preserves
what was printed rather than repairing the source text:

```json
{
  "relation_id": "r-unsupported",
  "support": "unsupported",
  "relation_kind": "uncertain",
  "evidence_structure": "uncertain",
  "context_requirement": "uncertain",
  "scope": "body_text",
  "anchor_spans": [{"start": 10, "end": 15, "text": "HDL1-PL"}],
  "source_error": {
    "flagged": true,
    "note": "Possible source typo; retain observed text",
    "proposed_text": "HDL2-PL"
  }
}
```

One-to-many alternatives are represented by `alternatives`; repeated
occurrences are separate relations with separate exact spans. Passage search is
stored as `not_searched`, `searched_none_found`, or `searched_found` and is not
derived from per-relation decisions. Each revision records reviewer identity,
time, source, and whether suggestions were exposed.
