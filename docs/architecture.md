# Target Architecture

## 1. System intent

The repository is an experimental platform for local abbreviation-definition extraction. It must make it easy to compare old pattern-based systems, modern rule systems, statistical models, transformer-based systems, and ensembles under identical data and evaluation contracts.

The evaluator and canonical data representation are the center of the repository. Algorithms are replaceable plugins.

## 2. Proposed package layout

```text
abbr-resolution/
  AGENTS.md
  pyproject.toml
  README.md
  configs/
    base.yaml
    corpora/
    resolvers/
    experiments/
  data/
    raw/                 # normally ignored or externally managed
    interim/
    processed/
    manifests/
  docs/
    architecture.md
    configuration.md
    scientific-contracts.md
    testing-and-quality.md
    decisions/
    tasks/
  experiments/
    runs/                # ignored/generated
  src/
    abbr_resolver/
      domain/
        models.py
        protocols.py
        errors.py
      config/
        models.py
        loader.py
      registry/
        core.py
        builtins.py
      corpora/
        base.py
        normalization.py
        validation.py
        serialization.py
        adapters/
      resolvers/
        base.py
        adapters/
        rules/
        learned/
      candidates/
      features/
      evaluation/
        matching.py
        metrics.py
        evaluator.py
      reporting/
      experiments/
      infrastructure/
        filesystem.py
        subprocess.py
        caching.py
      cli/
  tests/
    unit/
    contract/
    integration/
    regression/
    e2e/
    fixtures/
```

This is a target, not a requirement to create empty modules for appearances. Create a module when a task gives it real responsibility.

## 3. Core flow

```text
raw corpus source
    -> CorpusAdapter
    -> canonical Document + gold AbbreviationDefinition objects
    -> validation
    -> canonical dataset artifact + manifest

canonical Document
    -> Resolver
    -> predicted AbbreviationDefinition objects
    -> prediction artifact

predictions + gold
    -> MatchingPolicy
    -> matched/unmatched records
    -> Metrics
    -> Reporters
```

## 4. Domain interfaces

The exact names may evolve, but responsibilities must remain narrow.

### CorpusAdapter

Responsible for translating one source format into canonical domain objects plus source provenance. It must not decide global evaluation policy.

### Resolver

Consumes canonical documents and returns predictions. Resolver output must not depend on evaluator internals.

### CandidateGenerator

Optional lower-level extension point. Produces candidate short-form/long-form pairs or spans without necessarily accepting them as final definitions.

### MatchingPolicy

Defines how gold and predicted definitions are paired for scoring. Exact and relaxed matching should be separate implementations/configurations rather than conditionals embedded in a monolithic evaluator.

### Metric

Consumes match outcomes and emits named values and optional structured details.

### Reporter

Consumes evaluation/experiment results and renders JSON, TSV/CSV, HTML, Markdown, etc. Reporting must not alter scores.

## 5. Dependency constraints

- `domain` imports only standard-library typing/value-object dependencies.
- `corpora`, `resolvers`, `evaluation`, and `features` may depend on `domain` and shared config/registry abstractions.
- `evaluation` must not import concrete resolver implementations.
- corpus adapters must not import evaluator implementations.
- CLI may import application-level services but contains no parsing/evaluation science.
- infrastructure dependencies such as subprocess invocation stay behind narrow adapters.

## 6. Extension mechanism

All major strategy choices should be instantiated by registry key from typed YAML configuration.

Conceptual YAML:

```yaml
resolver:
  type: ab3p
  params:
    executable: /opt/ab3p/identify_abbr

matching:
  type: exact_pair
  params: {}

metrics:
  - type: pair_prf
    params:
      averaging: micro

reporters:
  - type: json
    params:
      pretty: true
  - type: html_error_report
    params:
      include_context_chars: 120
```

Construction should occur in an application composition layer. Domain objects should never load YAML or query a global registry themselves.

## 7. Data immutability and provenance

Canonical processed datasets should be treated as immutable artifacts identified by a manifest/fingerprint. A normalizer should emit a new artifact rather than modifying a source dataset in place.

Each annotation should preserve enough provenance to answer:

- Which source dataset/file/record did this come from?
- What were the original span coordinates and text?
- Which transformations were applied?
- Was anything repaired or inferred?
- Which adapter/version generated the canonical representation?

## 8. Failure philosophy

Fail fast on programmer/configuration errors. Accumulate and report expected dirty-data issues when safe to do so.

Examples:

- unknown registry key -> hard failure with available keys;
- malformed YAML -> hard failure with location/context;
- impossible span offset -> validation issue, with strict mode optionally converting to hard failure;
- external resolver crash -> structured resolver execution error with stderr/exit status captured;
- duplicate output -> governed by explicit deduplication policy.
