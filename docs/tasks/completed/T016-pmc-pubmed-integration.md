# T016 completion note

## Changed

- Added the `abrex.literature` adapter boundary for immutable local PubMed/PMC
  article and section representations, including PMID/PMCID and section
  provenance.
- Added registry-backed `sections` and `article` segmentation policies. The
  section policy preserves source text per canonical `Document`; the article
  policy joins sections with a configured separator and records canonical
  section intervals.
- Added `ArticleResolutionService`, which composes the existing YAML-selected
  resolver executor with article segmentation and maps validated predictions
  to downstream `ArticleEntity` records. No resolver or evaluator code was
  changed to understand literature sources.
- Added local JSON input and `article-resolutions-v1` output serialization plus
  the thin `abrex article resolve` CLI command.
- Added synthetic local-article configuration/examples and focused unit tests.
- Documented that retrieval/networking is outside this adapter and that spans
  crossing section boundaries remain observable mapping issues.

## Verification

- `env313\\Scripts\\python.exe -m ruff format --check src tests` — passed.
- `env313\\Scripts\\python.exe -m ruff check src tests` — passed.
- `env313\\Scripts\\python.exe -m mypy` — passed (`108` source/test files).
- `env313\\Scripts\\python.exe -m pytest tests/unit tests/contract --basetemp .pytest-tmp/t016-gate -q` — passed (`166` tests).
- Full coverage run with the repository-local pytest basetemp — passed (`170` tests, `95.72%`, above the configured `95%` floor).
- The checked-in local article example was resolved through the CLI and wrote
  a provenance-preserving output artifact.

## Unresolved issues

- T016 intentionally does not retrieve or parse NCBI network responses. A
  future adapter may translate a licensed PMC/PubMed XML/BioC client model
  into `Article`; that work should define source-specific parsing and title/
  section semantics in a separate task.
- Section-local offsets are unavailable for predictions that cross a join
  separator or multiple sections; these are retained with explicit mapping
  issues for downstream policy rather than assigned implicitly.
- Proposed follow-up task: add a licensed/local PMC/PubMed XML or BioC source
  adapter with an explicitly reviewed section/title extraction contract.
