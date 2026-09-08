# Contemporary annotation-pilot guidelines (T030-v1)

These operational rules define the pilot packet format. They do not settle
scientific policy for every future corpus; unresolved cases remain explicit.

## Label a relation, not just a string

Annotate the short form and its defining long form as one relation with a
stable `relation_id`. Use half-open Unicode character offsets against the exact
case text. For `long form (LF)`, the long-form span is `long form` and the
short-form span is `LF`; parentheses are context, not part of the short form.
The captured text must equal the text slice exactly.

Do not label an isolated `LF` without a supported long form as an accepted
relation. Keep the case or label unresolved when evidence is insufficient.

## Boundaries and difficult structures

- Include internal punctuation that belongs to the term (`A. beta`), but do
  not absorb surrounding punctuation, parentheses or sentence whitespace.
- Record repeated definitions as separate relations with separate IDs and
  spans. Do not collapse repeated or nested/overlapping definitions.
- Tables, table captions, table headers/cells, footnotes, definition lists and
  figure captions receive phenomenon tags. A pair across unrelated table cells
  is not inferred.
- Titles are labeled only when the protocol explicitly includes title text in
  the case. Otherwise title text remains metadata/context.
- If either span is unavailable, retain an unresolved/incomplete label rather
  than fabricating coordinates. Empty-definition documents are valid pilot
  cases and must remain in the packet.
- Ambiguous alternative long forms remain unresolved until adjudication; do
  not choose the most frequent dictionary entry as gold.

## Provenance and blindness

Every label records origin (`independent`, `assisted` or `adjudicated`),
annotator identity where applicable, guideline version, revision and history.
Assisted labels must name the suggestion source and are not independent gold.
Independent evaluation labels cannot carry resolver identity. Adjudication
changes are history events, not in-place erasure of earlier decisions.

The T030 importer emits accepted and incomplete labels into canonical records,
skips explicitly rejected labels, and preserves relation IDs in provenance.
Reports separately count independent, assisted, adjudicated and unresolved
labels. Without independent expert review, the packet is provisional/silver and
cannot support contemporary accuracy claims.
