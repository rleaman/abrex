# Candidate Generation Extension Point

`abrex.candidates` separates high-recall span-pair enumeration from resolver
acceptance, scoring, and evaluation. A `CandidateGenerator` consumes one
canonical `Document` and returns immutable `Candidate` values plus explicit
`CandidateDiagnostic` values for observations and pruning. Candidates use the
same Unicode half-open character offsets as the domain schema and retain
construction metadata and provenance.

Generators are selected through the injectable `GENERATORS` registry and a
typed YAML section:

```yaml
candidates:
  generators:
    - type: parenthetical
      params:
        maximum_long_form_words: 10
  deduplicate: false
```

The built-in `parenthetical` generator considers only non-nested parentheses
with an ASCII alphanumeric/hyphen short form and enumerates every preceding
word window up to the configured maximum. It does not align characters,
infer acceptance, normalize text, or score candidates. Unsupported syntax and
configured length/context exclusions are reported as pruning diagnostics.
Deduplication is disabled by default and, when enabled, emits a diagnostic for
each removed duplicate.

Candidate records can be serialized independently as deterministic
`candidates-v1` JSONL using `serialize_candidate_artifact` and
`read_candidate_artifact`, allowing later resolvers and scorers to consume
the artifact without importing evaluator code.

The bounded structural variants are `reverse_order`, which enumerates
`(SHORT) long form` constructions, `nested_parenthetical`, which retains
candidate windows for nested parentheses, and `structured_relations`, which
requires an `ArticleDocument` carrying T027 table/definition-list structures.
The structured generator groups same-row cells and term/definition items,
maps text only within declared canonical section locations, and records source
paths in provenance. Its `generate(Document)` method emits an explicit
metadata-required diagnostic rather than guessing structural relationships.
All variants have explicit text/complexity bounds and emit pruning diagnostics;
none accepts a candidate as gold or applies OCR to image-only regions.

The `lexical_resource` generator consumes one or more T028 SQLite resources.
For each raw variant it searches the canonical document for exact short- and
long-form occurrences within a configured character window. A missing local
span is explicitly pruned, and emitted candidates retain the source label and
resource SHA-256 in provenance. Aggregate counts do not create document
locations or resolve homonyms.
