# Scientific model of interpretive grounding

Status: provisional working model, iteration 0.1  
Evidence date: September 10, 2026

This directory is the home for Abrex's evolving scientific model: the concepts,
phenomena, distinctions, counterexamples and open questions discovered through
iterative modeling and annotation. It is deliberately separate from the
[annotation guidelines](../annotation-guidelines.md), which are the operational
instructions given to annotators, and from the
[scientific contracts](../scientific-contracts.md), which record choices that
have been frozen for implementation or evaluation.

Following the MATTER-cycle terminology used by Pustejovsky and Stubbs, the
current work is in an early "babbling" phase. The active loop is chiefly:

```text
model -> annotate -> revise model -> annotate -> ...
```

Claims here are therefore hypotheses under refinement, not automatically
annotation policy. A distinction becomes part of the annotation guidelines only
after it is made observable, supplied with positive and negative examples, and
given an explicit treatment for ambiguous cases. A distinction becomes a
scientific contract only when the project intentionally freezes its effect on
data representation, training or evaluation.

## Source and limits of the initial observations

The initial observations came from the completed T052 review state
[`review-packet-v2.annotations.json`](../../.artifacts/T052/review-packet-v2.annotations.json)
and its immutable source packet
[`review-packet-v2.json`](../../.artifacts/T052/review-packet-v2.json).

After final adjudication, the review state contains:

- 60 reviewed cases and 105 pair decisions;
- 103 decisions marked correct and two marked incorrect;
- no remaining `unsure` or `unreviewed` pair decisions;
- no remaining unresolved case-level missed-definition judgments;
- 79 Schwartz-Hearst suggestions, of which 77 were marked correct and two
  incorrect;
- 26 manually added definitions across ten cases; and
- six corrected suggestions, in addition to 73 unchanged assisted decisions.

The two rejected suggestions were informative boundary cases: a spurious
`D-group` pairing and an `arrow` pairing produced from figure-caption prose.
The review also exposed numerous valid but non-prototypical forms, including
compositional lipid labels such as `LDL5-TG`, anatomical or figure-local labels
such as `7n`, and definitions with coordination ellipsis, shared material or
source-text errors.

These counts are descriptive review dispositions, not precision, recall or
prevalence estimates. The packet was diagnostically selected, the judgments
were assisted, and Ab3P and PLODv2 were unavailable for the bounded run. All 79
machine suggestions came from Schwartz-Hearst. The PMC and PubMed arms and the
selection strata therefore cannot be treated as a representative benchmark.

## Initial interpretation

Abbreviation expansion appears to be one member of a wider family of
phenomena. The common property is not strict lexical equivalence. It is
**interpretive grounding**: evidence tells a reader how to interpret a compact
sign, code, label or marker.

```text
anchor or sign --grounded by evidence--> interpretation or referent
```

Examples differ in the relation that supplies the grounding:

```text
RCTs     --expands to--> randomized controlled trials
LDL5-TG  --encodes-->    triglycerides in LDL subclass 5
arrow    --points to-->  a depicted object identified by caption and geometry
```

`RCTs` is close to a reusable lexical equivalence. `LDL5-TG` is a
compositional code whose parts encode attributes of the referent. An arrow is
not an abbreviation at all: its caption can specify the conceptual class while
the image supplies the spatial connection to a particular depicted instance.
The arrow is included in the broad model only because it participates in an
interpretive-grounding relation, not because it should be accepted by an
abbreviation extractor.

This distinction explains why parenthetical form alone is insufficient.
Expressions resembling `description (label)` may introduce an abbreviation,
decode a local code, define a legend key, identify a visual marker, or merely
trigger a parser accidentally. Surface syntax proposes a candidate relation;
semantic and structural context determine its kind.

## Provisional hierarchy of phenomena

The following hierarchy is a working organization, not yet a mutually
exclusive label inventory:

1. **Interpretive grounding**
   1. **Lexical grounding**
      - abbreviation or acronym expansion;
      - alias, shorthand or scientific symbol.
   2. **Code and label grounding**
      - compositional code;
      - opaque or mnemonic document-local label;
      - experimental-group label.
   3. **Structured and multimodal grounding**
      - figure- or table-local label;
      - panel, color, line-style or shape key;
      - deictic visual marker such as an arrow or arrowhead.
2. **Non-grounding candidates**
   - accidental parenthetical matches;
   - unsupported associations;
   - malformed spans or source-text artifacts.

The negative branch is retained because it reveals where candidate-generation
syntax crosses the scientific boundary. It is not a positive subtype of
interpretive grounding.

## Provisional annotation taxonomy

A compact first taxonomy for a relation-level label is:

- `lexical_abbreviation`: a compressed lexical form and an explicit expansion;
- `compositional_code`: a form whose components systematically encode the
  description;
- `document_local_label`: an arbitrary or mnemonic label defined for local
  use;
- `figure_or_table_label`: a label whose interpretation is scoped to a
  structured object;
- `visual_marker`: a graphical sign whose target is grounded partly through
  position or geometry;
- `alias_or_symbol`: another explicit naming or symbol relation that is not an
  expansion;
- `not_a_relation`: a proposed pair that is not supported by the evidence; and
- `uncertain`: insufficient evidence or an unresolved scope decision.

This inventory should not be added mechanically to the annotation schema. It
first needs a small recoding exercise to test whether annotators can distinguish
the categories and whether some should instead be represented as independent
dimensions.

## Independent dimensions

The pilot suggests that a single flat class will discard useful structure.
Candidate relations can instead be described along independent dimensions:

### Anchor form

- lexical token or phrase;
- initialism, acronym or shortened form;
- compositional alphanumeric code;
- arbitrary or mnemonic label;
- graphical marker or layout feature.

### Grounding relation

- `expands_to`;
- `encodes`;
- `aliases`;
- `denotes`;
- `points_to`; or
- unsupported/no relation.

### Scope

- general or field-level;
- manuscript-local;
- section- or experiment-local;
- table-, figure- or panel-local.

### Referent level

- concept or class;
- named entity or textual object;
- set of instances;
- particular textual or visual instance.

### Required modality

- text alone;
- text plus document structure or layout;
- text plus table organization;
- text plus image and spatial geometry.

### Stability and reuse

- reusable throughout or beyond the manuscript;
- reusable only within a local scope;
- occurrence-specific and deictic.

### Conceptual specificity and referential localization

These should not be conflated. A caption may identify precisely what kind of
object an arrow marks while text alone cannot locate the particular object. In
the image, the same arrow may be spatially precise. The limitation is modality
dependence, not necessarily conceptual vagueness.

### Span and source structure

- contiguous expansion;
- coordination ellipsis or shared expansion material;
- discontinuous expansion;
- list, range or one-to-many relation;
- repeated or nested definition;
- source-text error or correction.

## Consequences for task definition and evaluation

The recommended design is a broad evidence layer plus named task projections:

1. Preserve candidate interpretive-grounding relations and their provenance.
2. Classify the relation and its relevant dimensions.
3. Derive a strict abbreviation-expansion view through an explicit policy.
4. Optionally derive broader code, local-label or multimodal grounding views.

This allows Abrex to retain scientifically useful labels without contaminating
strict abbreviation evaluation. A visual marker can be a valid grounding
phenomenon and still be a false positive for the abbreviation task.

Future reports must state which projection is being evaluated. Exact
short-form/long-form metrics remain appropriate for the current strict task,
but other relations may require different objects and metrics. For example, an
arrow relation may require a caption span, a graphical anchor and a visual
target region rather than two text spans.

No current canonical domain object or evaluator is changed by this document.
Operationalization requires an explicit task and a versioned update to the
guidelines, schema and evaluation policy.

## Human and model roles during model development

The ability of a language model to interpret individual cases does not by
itself justify replacing human annotation. During the babbling iterations, a
useful division of labor is:

- a model proposes first-pass spans, relation classes, dimensional labels,
  confidence and supporting evidence;
- the scientific lead defines the ontology and adjudicates boundary cases;
- the scientific lead reviews disagreements, low-confidence cases and a random
  sample of high-confidence cases; and
- calibration results determine whether the human audit fraction can safely be
  reduced.

Model-produced or model-visible judgments remain assisted or silver unless
independently verified. A model must not produce both the test annotations and
the predictions used to claim its own accuracy. Research evaluation should
retain a smaller locked set annotated independently and blind to evaluated
system output, ideally with dual annotation or an independently reviewed
subset.

The intended outcome is therefore not to remove the human scientific role. It
is to move scarce human effort from routine first-pass labeling toward model
definition, difficult adjudication and calibration.

## Candidate workflow for the next M-A iterations

1. Recode the accepted and rejected T052 relations using the provisional
   taxonomy and dimensions.
2. Record examples that cannot be represented cleanly rather than forcing a
   class.
3. Revise the hierarchy and merge or split categories based on observed
   disagreements.
4. Convert stable distinctions into concrete annotation questions and examples.
5. Pilot model-first annotation with human review and a random high-confidence
   audit.
6. Measure agreement and error by relation kind, scope, modality and span
   structure.
7. Freeze only the task projections needed for a particular training or
   evaluation run.

Each iteration added beneath this document, or in a dated companion document,
should record the evidence packet, model version, guideline version, observed
counterexamples, proposed changes and unresolved questions. Earlier iterations
should remain available as scientific history rather than being silently
rewritten.

## Open questions

- Is `interpretive grounding` the best durable umbrella term?
- Which relation kinds belong within Abrex's core scope, and which should be
  retained only as diagnostic neighboring phenomena?
- When is a compositional description explicitly grounded rather than inferred
  from domain knowledge?
- Should local labels be propagated outside the sentence, figure or table in
  which they are introduced?
- How should shared, discontinuous and one-to-many expansion evidence be
  represented?
- What is the minimum useful representation for a multimodal marker: caption
  span, marker type, image coordinates, target region, or some combination?
- Which independent dimensions are reliable enough for human and model
  annotation?
- What independently annotated sample is sufficient to calibrate model-first
  annotation and preserve credible evaluation?
