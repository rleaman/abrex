# Numbered Codex Assignments

## Current completion roadmap

The September 6, 2026 planning review adds **T017–T048** (revised September 7), all initially
planned for GPT-5.6 Luna. Start with the [completion plan](../project-completion-plan.md),
[current-state audit](../project-state-audit.md) and
[Luna execution guide](LUNA_EXECUTION_GUIDE.md).

T049 was added September 8, 2026 as a focused Luna maintenance task to make
historical dataset downloads selective, idempotent, and consistent with the
single/group corpus-build CLI.

T000–T016 below are the historical implementation sequence. Their completion
notes describe the scope delivered, not proof that the full research project
is finished. The tentative T017–T023 suggestions in the Word handoff are
superseded by the new repository assignments. Creating this backlog does not
authorize implementing it automatically.

T017 is complete for the environment and CI engineering scope. See the
[T017 completion note](completed/T017-reproducible-development-environments.md).
T018 is complete for the reproducible WSL Ab3P build and upstream verification
scope. See the [T018 completion note](completed/T018-build-and-verify-real-ab3p.md).
T019 is complete for the historical adapter engineering and local-source audit
scope. See the [T019 completion note](completed/T019-audit-and-repair-corpus-semantics.md).
T020 is complete for the typed runtime, cache-identity and ABREX-on-WSL smoke
scope; see the [T020 completion note](completed/T020-ab3p-runtime-and-cache-identity.md)
and [WSL runtime verification](../wsl-runtime.md).
T021 is complete for the native offset adapter and live conformance scope; see
the [T021 completion note](completed/T021-ab3p-native-offset-adapter.md).
T022 is complete for the bounded real-data baseline smoke and reproducibility
scope; see the [T022 completion note](completed/T022-real-baseline-smoke-benchmarks.md).
T023 is complete for the typed PLODv2 detector, independent span artifacts,
window/offset handling and optional-runtime integration. See the
[T023 completion note](completed/T023-plodv2-span-detection.md) and
[PLOD runtime setup](../plod-runtime.md). The current shell cannot launch the
documented Ubuntu WSL distribution, so the supplied real-checkpoint smoke is
reported as an environment limitation rather than new evidence.
T024 is complete for explicit position-anchored and named greedy pairing,
composition with T023, and deterministic pair policies. See the
[T024 completion note](completed/T024-plodv2-pairing-resolver.md). T031 is
ready once the historical comparison inputs are assembled.
T041 is complete for generic bounded, resumable shard orchestration; see the
[T041 completion note](completed/T041-resumable-bounded-corpus-processing.md).
T025 is complete for bounded PubMed EFetch acquisition, manifest/replay
engineering and its two-record live pilot; see the [T025 completion note](completed/T025-literature-acquisition-manifests.md).
T026 is complete for local PubMed XML/BioC parsing, source provenance and its
bounded live round-trip scope; see the [T026 completion note](completed/T026-pubmed-bioc-source-parsing.md).
T027 is complete for JATS structural preservation and bounded real-source
validation; see the [T027 completion note](completed/T027-jats-tables-captions-and-definition-lists.md).
T028 is complete for the provenance-preserving resource layer and bounded
frequency-resource pilot; see the [T028 completion note](completed/T028-lexical-resource-ingestion.md).
T029 is complete for deterministic contemporary sampling proposals and
article-level leakage controls; see the [T029 completion note](completed/T029-sampling-and-leakage-controls.md).
T030 is complete for the versioned annotation workflow and bounded provisional
pilot; independent review and gold certification remain pending. See the
[T030 completion note](completed/T030-annotation-pilot-and-adjudication.md).
T047 is complete for the deterministic bounded corpus-selection mechanism and
metadata-frame proposal; final work-scale limits and scientific approval remain
open. See the [T047 completion note](completed/T047-large-scale-corpus-selection.md).
T046 is complete for bounded ADAM and ALLIE acquisition/import pilots; see
the [T046 completion note](completed/T046-external-dictionary-acquisition.md).
T048 is complete for bounded runtime verification, typed integration and the
T022 resolver artifact. See [runtime instructions](../bioadi-runtime.md) and
the [T048 completion note](completed/T048-bioadi-runtime-and-resolver.md).

Execute T046 after T028 and before T034. Design T047 after T029 and finalize it before T042; task identifiers were preserved rather than renumbered. See the [resource acquisition register](../resource-acquisition-register.md) for ADAM and additional suggestions.

T048 assesses the BioADI JAR after T022 and supplies additional benchmark results if viable. The [complete resource catalog](../resource-catalog.md) preserves all 41 supplied CSV entries and their task routes.

T049 is complete for the idempotent, group-driven dataset downloader; see the
[T049 completion note](completed/T049-idempotent-dataset-download-cli.md).

### Planned assignments

| Task | Outcome | Hard new prerequisites | Milestone |
| --- | --- | --- | --- |
| [T017](T017-reproducible-development-environments.md) | Make development and experiment environments reproducible | Current baseline | A |
| [T018](T018-build-and-verify-real-ab3p.md) | Build and verify real Ab3P in the existing Ubuntu environment | T017 | A |
| [T019](T019-audit-and-repair-corpus-semantics.md) | Audit historical corpus semantics and prevent silent annotation changes | T017 | A |
| [T020](T020-ab3p-runtime-and-cache-identity.md) | Make Ab3P resource lookup and cache identity reliable | T018 | A |
| [T021](T021-ab3p-native-offset-adapter.md) | Use verified Ab3P offsets for canonical span mapping | T020 | A |
| [T022](T022-real-baseline-smoke-benchmarks.md) | Run reproducible real-data baseline benchmarks | T019, T021 | A |
| [T023](T023-plodv2-span-detection.md) | Integrate PLODv2 as a reproducible span detector | T017, T019 | B |
| [T024](T024-plodv2-pairing-resolver.md) | Add explicit PLODv2 pairing strategies and resolver integration | T023 | B |
| [T025](T025-literature-acquisition-manifests.md) | Acquire bounded literature snapshots with source manifests | T017 | B |
| [T026](T026-pubmed-bioc-source-parsing.md) | Parse local PubMed and BioC articles with traceable text | T025 | B |
| [T027](T027-jats-tables-captions-and-definition-lists.md) | Preserve full-text tables captions and definition lists | T026 | B |
| [T028](T028-lexical-resource-ingestion.md) | Build a provenance-preserving abbreviation resource layer | T017 | B |
| [T029](T029-sampling-and-leakage-controls.md) | Define contemporary sampling and article-level data separation | T019, T026, T027 | B |
| [T030](T030-annotation-pilot-and-adjudication.md) | Create an auditable contemporary annotation pilot | T029 | B |
| [T031](T031-comparative-benchmark-and-oracle-analysis.md) | Measure resolver complementarity and uncertainty | T022, T024 | C |
| [T032](T032-transparent-hybrid-resolver.md) | Implement an evidence-driven transparent hybrid | T031 | C |
| [T033](T033-structural-candidate-generators.md) | Generate candidates for difficult prose and full-text structures | T027, T031 | D |
| [T034](T034-lexical-candidates-and-evidence-features.md) | Use dictionaries and terminologies as local candidate evidence | T028, T029, T033, T046 | D |
| [T035](T035-weak-evidence-ledger-and-silver-labels.md) | Represent noisy evidence and derive versioned silver labels | T032, T034 | D |
| [T036](T036-contextual-pattern-induction.md) | Induce and validate reusable contextual patterns | T035 | D |
| [T037](T037-training-dataset-materialization.md) | Build leakage-safe candidate training datasets | T030, T035, T036 | D |
| [T038](T038-lightweight-scorer-training.md) | Train and evaluate a lightweight candidate scorer | T037 | D |
| [T039](T039-controlled-iteration-controller.md) | Implement bounded evidence and model iteration | T036, T038 | D |
| [T040](T040-research-validation-and-ablation-campaign.md) | Test the denoising hypothesis and select the release candidate | T030, T031, T039 | E |
| [T041](T041-resumable-bounded-corpus-processing.md) | Make corpus processing resumable and bounded in memory | T022, T025 | E |
| [T042](T042-tagged-corpus-and-dictionary-build.md) | Build the tagged literature corpus and expanded dictionary | T028, T040, T041, T047 | E |
| [T043](T043-document-local-mention-propagation.md) | Link abbreviation mentions to local definitions | T026, T032 | F |
| [T044](T044-downstream-impact-evaluation.md) | Measure impact on the biomedical NLP pipeline | T040, T043 | F |
| [T045](T045-release-and-reproducibility-package.md) | Package the resolver and research resources for reuse | T040, T042, T044, T048 | F |
| [T046](T046-external-dictionary-acquisition.md) | Acquire and audit external abbreviation dictionaries | T028 | B |
| [T047](T047-large-scale-corpus-selection.md) | Select and freeze the large-scale literature corpus | T025, T029 | B/E |
| [T048](T048-bioadi-runtime-and-resolver.md) | Verify BioADI software and integrate if viable | T017, T019, T022 | B/C |
| [T049](T049-idempotent-dataset-download-cli.md) | Make dataset downloads selective, idempotent and group-driven | T011, T017 | Maintenance |

## How to use these tasks

The user can assign work by saying, for example, `Implement T006` or `Take T003 and T004`.

Before starting any task, Codex must read:

- `AGENTS.md`;
- `START_HERE_FOR_CODEX.md`;
- the assigned task;
- any dependencies listed in that task;
- relevant architecture/scientific docs.

Do not treat task numbering as permission to ignore dependencies.

## Task map

| Task | Title | Depends on | Research oversight |
| --- | --- | --- | --- |
| T000 | Bootstrap repository | none | low |
| T001 | Config and registry infrastructure | T000 | low |
| T002 | Core domain schema and provenance | T000 | medium |
| T003 | Corpus adapter framework | T001, T002 | low/medium |
| T004 | Canonical validation and serialization | T002, T003 | medium |
| T005 | Resolver interface and execution contract | T001, T002 | low |
| T006 | Evaluation matching engine | T002, T004 | high on semantics, low on implementation |
| T007 | Ab3P baseline adapter | T005 | low |
| T008 | Regression/golden baseline suite | T004, T006, T007 | medium |
| T009 | Error-analysis/reporting framework | T006 | low/medium |
| T010 | Experiment runner and reproducibility | T001, T004, T005, T006 | low |
| T011 | Historical corpus adapters | T003, T004 | medium |
| T012 | Schwartz-Hearst baseline | T005, T008 | medium |
| T013 | Candidate-generation framework | T001, T002, T008 | medium/high |
| T014 | Feature extraction framework | T001, T013 | medium |
| T015 | Learned scorer/ranker scaffold | T010, T013, T014 | high |
| T016 | PMC/PubMed production adapter | T005, T010 | medium |

## Recommended waves

### Wave A - substrate
T000 through T010, with T006 scientific semantics reviewed by the user.

### Wave B - benchmark breadth
T011 and T012.

### Wave C - new-method research
T013 through T015.

### Wave D - production integration
T016.
