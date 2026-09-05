# Learned scorer extension point

`abrex.scorers` provides the plumbing for supervised candidate scoring without
choosing a label definition, model family, loss, split strategy, or threshold
selection rule. A scorer receives the T014 `FeatureMatrix` and caller-owned
numeric labels through `ScoringDataset`; it returns one finite score per
candidate row.

Scorers are selected through the injectable `SCORERS` registry. A custom
implementation must expose `identity`, `version`, `fit(train, dev, seed)`, and
`predict(features)`. Implement `save(path)` and `load(path)` to participate in
fingerprinted model artifact persistence. No sklearn or model dependency is
required by the framework.

## Configuration hooks

The typed composition shape is:

```yaml
scorer:
  type: my_scorer
  params: {}
  calibration:
    type: identity
    params: {}
  selection:
    type: fixed
    params:
      value: 0.5
  seed: 20260905
  feature_config_fingerprint: sha256-of-resolved-feature-config
```

Calibration and selection are optional. Calling materialization without an
explicit selection policy fails rather than silently turning a score into a
prediction. The built-in `identity` calibrator and `fixed` threshold are
plumbing components; the fixed threshold is only active when explicitly
configured. Other calibration and ranking policies belong in registered
plugins.

## Split manifests

Splits are consumed from a checked-in JSON manifest. The framework requires
explicit, non-overlapping document assignments and never creates a random
split:

```json
{
  "schema_version": "scorer-splits-v1",
  "train": ["doc-train"],
  "dev": ["doc-dev"],
  "test": ["doc-test"]
}
```

`partition_dataset` preserves feature row order and uses the supplied labels;
it does not infer labels from gold annotations. The scientific label policy
and split rationale remain part of the experiment record.

## Artifacts and predictions

`write_scorer_artifact` writes model state plus a sidecar manifest containing
the scorer key/version, model SHA-256, ordered feature-schema fingerprint,
optional resolved feature-config fingerprint, seed, and configured strategy
identities. Readback verifies these values before loading the model through an
injected registry.

`materialize_predictions` bridges selected candidates to the existing resolver
`PredictionRecord` contract. Prediction metadata retains the scorer identity,
model artifact fingerprint, and feature configuration fingerprint. Candidate,
evaluator, and reporting contracts are unchanged.
