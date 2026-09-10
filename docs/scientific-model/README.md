# Scientific-model iterations

This directory records the evolving scientific model behind Abrex. It is the
workspace for phenomena, distinctions, counterexamples and provisional
decisions discovered through repeated modeling and annotation.

Following the early, iterative portion of the MATTER cycle described by
Pustejovsky and Stubbs, the working loop is:

```text
model -> annotate -> revise model -> annotate -> ...
```

## Documentation lifecycle

Each meaningful modeling checkpoint receives a dated Markdown document. Once
recorded, that document is historical evidence and must not be rewritten to
match later thinking. Corrections, disagreements and superseding decisions go
in a later iteration that links back to the earlier one.

Use filenames of the form:

```text
YYYY-MM-DD-short-descriptive-title.md
```

If more than one checkpoint is needed on the same date, make the descriptive
titles distinct. Each iteration should record, where applicable:

- the evidence packet or annotation batch;
- the model and guideline versions in use;
- observations and representative examples;
- provisional definitions, hierarchy and dimensions;
- counterexamples and unresolved questions;
- decisions proposed, accepted, rejected or deferred; and
- consequences proposed for later annotation or evaluation.

The dated files describe what was believed or proposed at a particular point;
they are not automatically current annotation policy.

## Relationship to operational documentation

The documentation layers have different responsibilities:

- **Scientific-model iterations:** provisional descriptive and theoretical
  work, preserved as an append-only history.
- **[Annotation guidelines](../annotation-guidelines.md):** versioned,
  annotator-facing rules that operationalize sufficiently stable distinctions.
- **[Scientific contracts](../scientific-contracts.md):** choices intentionally
  frozen for data representation, training or evaluation.
- **Architecture decision records:** long-lived software architecture choices,
  not the routine history of scientific-model revision.

A proposal moves from a scientific-model iteration into the annotation
guidelines only when it is observable, has positive and negative examples, and
specifies how uncertainty is recorded. It affects implementation or evaluation
only through an explicit task and corresponding contract or schema change.

## Iteration index

| Date | Iteration | Evidence and focus | Status |
| --- | --- | --- | --- |
| 2026-09-10 | [Interpretive grounding from the T052 pilot](2026-09-10-interpretive-grounding.md) | Initial hierarchy, taxonomy and independent dimensions derived from the 60-case assisted review; [frozen evidence](../../evidence/T052/README.md) | Provisional; preserved |
