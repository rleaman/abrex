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
