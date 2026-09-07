# Project state audit

Reviewed on September 6, 2026, against checkout `1fc65f4` (Implemented T016). This is a planning audit of the supplied documents, all T000–T016 completion notes, repository documentation, selected implementation paths and current checks. It is not a full scientific code review or a new real-corpus benchmark.

## What the sources establish

The user's [original idea](../handoff/idea.txt) proposes an iterative system in which detectors, lexical resources and literature help denoise one another. Its three desired research outputs are a tagged literature corpus, an expanded abbreviation dictionary and better extraction methods, with little routine work for the scientist.

The [vision](../handoff/abbreviation_resolution_project_vision.docx) emphasizes a practical local-definition resolver and downstream entity extraction. The [handoff](../handoff/abbreviation_resolution_project_handoff.docx) proposes real runs, PLODv2, frequency resources, contemporary annotation and fusion. Those are useful hypotheses and priorities, not binding instructions. In particular, the vision's cell-phenotype example is not evidence that a downstream evaluation dataset exists.

The new plan preserves the practical resolver milestone and restores the original idea's iterative learning and resource outputs. Its T017–T045 numbers are the new repository plan; the handoff's tentative T017–T023 numbering was never implemented and is superseded by the new task files.

## Implementation and completion logs

| Existing tasks | Verified implemented scope | Remaining distinction |
| --- | --- | --- |
| T000–T005 | Package/config/registry, canonical models, corpus pipeline, serialization and resolver execution | Established infrastructure, not evidence of extraction quality |
| T006 | Exact pair matching; later code also provides exact span evaluation | Partial annotations and task-specific scoreability still require careful corpus interpretation |
| T007–T008 | Ab3P subprocess/cache adapter and synthetic parser/reconstruction golden cases | No verified live Ab3P benchmark artifact in this checkout |
| T009–T010 | Reports, experiment runner, separate run/prediction identities and manifests | Comparative analyses, atomic publication, larger-scale execution and full external identities need follow-up |
| T011 | Historical adapters and seven current corpus configurations | Real data files are not present here; earlier logs describe other local states |
| T012 | Dependency-free Schwartz–Hearst implementation | Explicitly limited to preceding LF with parenthetical SF; not a complete reproduction of every variant |
| T013–T014 | Parenthetical candidate enumeration and numeric feature framework | Difficult prose and table/caption candidate coverage remains unimplemented |
| T015 | Training/scoring interfaces, persistence, calibration/selection hooks and learned resolver adapter | No registered trained scientific model or defined label-construction pipeline |
| T016 | Local Article JSON, section/article segmentation, resolution and downstream source mapping | No PubMed retrieval, real XML/JATS parser, structured table support or article-wide mention propagation |

The handoff mentions an older 158-test/96.47% snapshot. T016 reports 170 tests and 95.72% coverage. Current verification agrees with T016, not the older handoff snapshot.

BADREX documentation is inconsistent: docs/historical-builds.md and portions of the T011 historical note describe corrected variants, while the current registry/group/config files omit them and docs/badrex-availability.md records unavailable sources. Do not invent missing configurations or presume a currently available source from the old log. T017/T019 reconcile this.

## Checks actually run

| Check | Current result |
| --- | --- |
| Ruff format | Passed, 108 files |
| Ruff lint | Passed |
| mypy | Passed, 108 source/test files |
| Unit and contract suite | 166 passed |
| Full offline suite | 170 passed |
| Statement coverage | 95.72%, above the configured 95% floor |

Checks used `env313/Scripts/python.exe`, Python 3.13.14. Initial sandbox launches were denied; scoped host access allowed them to run. An initial pytest attempt failed because the `.pytest-tmp` parent did not exist. Creating that parent and using fresh task-local basetemp paths resolved it. These were execution-environment issues, not code test failures.

Full command: `env313/Scripts/python.exe -m pytest --cov --cov-report=term --basetemp .pytest-tmp/planning-full -q --tb=short`.

No compiler installation, Ab3P build, model inference, historical dataset download, algorithm fix or scientific experiment was performed in this planning task. Application source, tests and previous completion logs were preserved.

## Ab3P environment and integration findings

- The sibling [Ab3P README](../../Ab3P/README.md) and Makefiles identify a C++ library requiring NCBITextLib, generated WordData and an upstream `make test` comparison. Both Makefiles still contain NCBITEXTLIB placeholders.
- Windows PATH inspection did not find a native C++ compiler or make. However, Ubuntu is already installed under WSL2, and a direct capability check found `/usr/bin/g++`, `/usr/bin/make`, `/usr/bin/python3` and `/usr/bin/git`. Their versions and Python compatibility are not yet verified. A new compiler installation is therefore not the first action.
- NCBITextLib is not part of the supplied source tree. Its machine-wide availability was not exhaustively searched. Build and pin it as needed in T018.
- `run_ab3p` currently inherits the application's working directory; the source distribution needs a valid `path_Ab3P`/WordData location. Arbitrary-directory execution is unverified (T020).
- Ab3P raw caching permits an installation label; the resolver has no automatic `cache_identity` method covering actual binary/resource content for the experiment runner. Explicit configured hashes can help, but label-only configurations do not establish immutable installation identity (T020).
- Text-only reconstruction enumerates all matching LF/SF occurrences, only accepts LF-before-SF, and raises on ambiguity. Repeated definitions or later SF reuse can prevent resolution. Upstream `AbbrOut` exposes `sf_offset` and `lf_offset`; T021 verifies their units and correctness before using them.
- Existing synthetic golden outputs remain valuable parser tests. They must not be overwritten and relabeled as real upstream results.

## Scientific risks visible in code

These are confirmed implementation paths with unmeasured real-data impact. They motivate focused tasks rather than an assertion that all existing benchmark data are wrong.

1. In `corpora/adapters/historical.py`, `_pair_entities` falls back to zipping independent SF/LF entity lists when relations are absent. Unequal lists can discard entities; unsupported relationship assumptions can create artificial gold pairs.
2. BioC annotation parsing takes one location and may omit unmatched entities or invalid relation endpoints. T019 requires complete loss/ambiguity accounting and explicit handling of discontinuous spans.
3. `_bioc_json_document` writes annotation text into the reconstructed source text. Annotation disagreements can therefore modify resolver input; T019 separates source preservation from named, audited repairs.
4. SDU@AAAI-22 AE supplies independent spans and must use span evaluation. SDU AD expansions may not occur locally. Neither should be forced into a local pair benchmark. The current code already preserves this important distinction for these adapters.
5. The supplied PLOD helper's `check_match` searches the full passage for the candidate strings. A matching construction elsewhere can affect the cost of the current candidate positions. It also merges adjacent same-type spans, uses greedy one-to-one pairing, loads an unpinned checkpoint and clears BioC annotations/relations before writing output. T023/T024 preserve useful ideas while replacing these assumptions with explicit tested contracts.
6. The current experiment runner and artifact writers are designed for small materialized runs. Resumable shards, atomic completion and measured memory limits are needed before work-scale processing (T041).

## The supplied 2024 frequency resource

During planning the user supplied [abbr_frequency_2024.json.gz](../data/raw/resources/abbr_frequency_2024.json.gz) and confirmed substantial CPU/GPU resources at work, with small pilots preferred now.

A bounded-memory traversal of the complete gzip JSON found a top-level mapping `SF -> {LF: integer count}`:

| Observed property | Value |
| --- | ---: |
| Compressed bytes | 133,582,426 |
| Distinct top-level SF strings | 2,342,940 |
| Decoded SF/LF variant entries | 12,473,609 |
| Sum of supplied counts | 82,035,444 |
| Pair entries with count 1 | 9,388,429 |
| Negative or non-integer count values encountered | 0 |
| Duplicate top-level SF keys encountered | 0 |
| LF variants containing `&amp;`, `&quot;` or `&#` | 171,590 |

Compressed-file SHA-256: `eec42cb74577130f07cdd2422f664b21011e4fdd70847ffe5b5345f63c78f023`.

This was a structural/count inspection, not a validity judgment on 12 million pairs. Nested duplicate JSON keys were not separately audited. Case variants, markup/entity strings and rare pairs must not be silently collapsed or discarded. Singleton frequency alone does not establish that a pair is false.

The file contains aggregate variants/counts, without per-article identifiers or contexts. The counts' unit, extraction installation, year inclusion, abstract/full-text overlap handling and source denominator are not encoded in this shape. The GPT documents describe an Ab3P-derived 2024 resource; preserve that as reported provenance until a run manifest or equivalent information confirms it. The sum cannot yet be described as distinct documents or true definition occurrences.

T028 can now implement the actual streaming importer. Sampling can use these counts to prioritize forms, but coverage-based article selection requires an occurrence index from literature text. Benchmark contamination cannot be ruled out for an aggregate resource without source identities; report resource-assisted results separately where that uncertainty persists.

## Sources checked for planning

- [Official Ab3P repository](https://github.com/ncbi-nlp/Ab3P): build dependency, resource lookup and upstream test contract, consistent with the local copy.
- [Official NCBITextLib repository](https://github.com/ncbi-nlp/NCBITextLib): dependency source.
- [PLODv2 checkpoint card](https://huggingface.co/surrey-nlp/flair-abbr-pubmed-filtered): checkpoint identity, span-oriented results and displayed CC-BY-SA-4.0 license. This does not verify installed runtime compatibility or pair accuracy.
- [PLODv2 paper](https://aclanthology.org/2024.lrec-main.270/): character-model and revised-dataset context. The linked PLODv2 GitHub repository could not be fetched through the browser during this audit; that is not evidence that it is unavailable.
- [PMC Open Access Subset guidance](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/): automated retrieval services and article-specific reuse terms. T025 must recheck the chosen service when implemented.

The [completion plan](project-completion-plan.md) turns these findings into bounded assignments and identifies the remaining scientific inputs.

## September 7 follow-up

The user supplied a sibling NCBITextLib source tree. Its README, include/, lib/ and applications/ were inspected; the September 6 dependency-availability statements above remain historical. T018 now uses this copy and builds in a writable task-owned location. No compilation was performed in this plan revision.

The user identified missing explicit dictionary-acquisition and large-scale document-selection work. T046 now covers external resources beginning with ADAM; T047 selects the discovery/training and tagged-release corpus. The revised plan has 31 assignments, T017–T047, with T046/T047 scheduled by dependency rather than numeric order.

## September 7 resource CSV follow-up

The user supplied Abbreviation Resolution Resources.csv with 41 records. The [catalog](resource-catalog.md) preserves every row and citation, distinguishing tools, corpora, dictionaries, reviews and unverified references. BioADI software is separate from the existing BioADI corpus adapter. A HEAD check of the supplied JAR returned HTTP 200, 5,237,679 bytes and application/x-java-archive; no download or execution occurred. Official ALLIE download listings and Acromine REST documentation were also reachable. T048 now covers BioADI runtime feasibility and conditional integration, bringing the planned assignments to 32 (T017–T048). Earlier counts above remain dated history.
