# T066 locked prediction-blind annotations

The scientific lead completed and locked all 32 fresh cases on October 5,
2026. The original annotation state and lock remain unchanged in
`evidence/T065`.

The first post-lock audit passed all integrity checks and identified two
relations left `unsure`. Before any evaluated predictions were run or exposed,
the scientific lead clarified that Cases 12 and 30 should both be ordinary
`abbreviation_expansion` relations with `contiguous_shared` evidence and
`text_alone` context.

The authoritative T067 inputs are:

- `review-packet-blind-v1.annotations.corrected-v2.json`;
- `review-packet-blind-v1.annotations.corrected-v2.lock.json`.

`correction-manifest-v2.json` records the exact authorization, before/after
fields, source and replacement hashes, and invariants. The correction appended
one `json_import` revision to each affected case; prior history, endpoints,
unrelated cases, and unrelated relations are unchanged.

`lock-audit-corrected-v2.json` confirms 32/32 ready cases, 40 relations all in
`correct` status, no uncertain or duplicate relations, matching state/lock
digests, and continued prediction blindness.

The context taxonomy follow-up requested during review is recorded in
`docs/annotation-guidelines.md`: future work should consider a separate
`background_knowledge` label or flag. It does not alter this frozen evaluation.
