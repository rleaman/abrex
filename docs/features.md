# Feature Extraction Extension Point

`abrex.features` turns T013 candidate artifacts into an immutable numeric
matrix. A `FeatureExtractor` receives only a canonical `Document` and one
`Candidate`; it never receives gold annotations or an evaluator. It declares a
stable identity, version, ordered feature names, descriptions, and an
`extract(document, candidate)` method returning finite numeric values.

Feature sets are composed through the injectable `EXTRACTORS` registry and
the typed YAML shape:

```yaml
features:
  extractors:
    - type: character_alignment
      params:
        case_sensitive: false
        ignore_non_alphanumeric: true
    - type: token_counts
      params: {}
    - type: length_relationship
      params: {}
    - type: position_direction
      params: {}
    - type: lexical_cues
      params:
        cues: ["abbreviated as", "also known as", "defined as"]
    - type: parenthetical_metadata
      params: {}
```

The configured order is the matrix column order. `ConfiguredFeatureSet` emits
a `FeatureMatrix` with `FeatureSchema` metadata, candidate row keys, and
numeric tuples; no NumPy or pandas dependency is required. Records are sorted
by document ID during artifact extraction, while candidates retain their
artifact-local order so rows can be joined back to candidate records using
`(document_id, candidate_index)`.

Built-in extractors are deliberately descriptive rather than acceptance
rules: character alignment uses configurable longest-common-subsequence
statistics, token counts use a configurable regular expression, and all
ratios return `0.0` when their denominator is zero. Capitalization,
digit/punctuation, length, position/direction, lexical cues, and parenthetical
construction metadata are separate components. Their parameters remain part
of the resolved experiment YAML, which is saved by the experiment runner.

Custom extractors should be registered in a local registry for embedding or
tests. They must use unique lowercase feature names and return the declared
keys; the feature set validates schema consistency, finiteness, and row width.

The built-in registry keys are:

`character_alignment`, `token_counts`, `capitalization`,
`digit_punctuation`, `length_relationship`, `position_direction`,
`lexical_cues`, and `parenthetical_metadata`.
