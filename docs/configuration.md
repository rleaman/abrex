# Configuration and Registry Contract

## Goals

Configuration should make experiments declarative, reproducible, composable, and inspectable. Registry hooks should make implementations replaceable without adding central dispatch conditionals.

## Configuration layers

Support deterministic merging of a small number of explicit layers, for example:

1. built-in defaults;
2. base project YAML;
3. component YAML fragments;
4. experiment YAML;
5. explicit CLI overrides.

The final resolved configuration must be validated into typed models and saved with each experiment run.

Avoid a configuration system so magical that it becomes difficult to determine the actual value of a setting. Prefer transparent merge semantics and a `config resolve` command that prints the final configuration.

Layers are merged in the order supplied to the loader: mappings are merged
recursively, while lists and scalar values are replaced by the later layer.
Environment expansion is explicit: `${VARIABLE}` expands inside a string and
`!env VARIABLE` expands a whole YAML scalar. Missing variables are
configuration errors; ordinary strings are not modified.

## Registry-backed component spec

Use a common shape:

```yaml
component_name:
  type: stable_registry_key
  params:
    key1: value1
```

For lists:

```yaml
reporters:
  - type: json
    params: {}
  - type: html_error_report
    params:
      context_chars: 120
```

The application composition layer resolves `type` against the appropriate registry and validates `params` against the implementation's configuration model or factory signature.

For example, a test or application can define a local registry and compose a
component without global import scanning:

```python
from pydantic import BaseModel

from abrex.config import ComponentSpec, create_component
from abrex.registry import Registry


class ToyParams(BaseModel):
    greeting: str


components = Registry[str]("components")
components.register("toy", lambda greeting: greeting, config_model=ToyParams)
result = create_component(
    ComponentSpec(type="toy", params={"greeting": "hello"}), components
)
assert result == "hello"
```

## Registry keys

Registry keys are public API. Prefer short, descriptive, lowercase snake_case keys such as:

- `ab3p`
- `schwartz_hearst`
- `exact_pair`
- `relaxed_boundary`
- `pair_prf`
- `json`
- `html_error_report`

Do not use Python import paths as the normal user-facing identifier.

## Configuration validation

Use Pydantic v2 models consistently for configuration validation. Do not mix
multiple configuration-validation paradigms without need.

Validation errors must be actionable and include the configuration path where possible.

## Secrets and machine-local paths

Do not commit machine-specific executable paths or secrets into canonical experiment config. Support environment-variable interpolation or a separate ignored local configuration layer for such values.

Environment interpolation must be explicit and documented.

## Seeds

A top-level experiment seed should exist even before learned models are introduced. Components that use randomness should derive deterministic child seeds from the experiment seed or explicitly document their seed behavior.

## Example base configuration

See `docs/examples/base.yaml`.

## Experiment runner

An experiment configuration uses `corpus.params.path` to point at an existing
canonical JSONL artifact, then selects resolver, matching, metrics, and
reporters through their registries. Run one with:

```console
python -m abrex experiment run docs/examples/experiment-toy.yaml
```

Set `output.reuse_cached_predictions: true` to reuse only a validated,
content-addressed prediction artifact. The runner writes a reproducibility
manifest, evaluation artifact, predictions, and configured reports beneath the
content-addressed run directory.
