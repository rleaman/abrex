# Completion plan for abrex

Prepared September 6, 2026; revised September 7, 2026. This plan delivers 32 proposed implementation assignments, T017–T048, for GPT-5.6 Luna. It builds on the completed T000–T016 framework. It does not authorize automatic execution of the backlog, installation of new systems, paid jobs or external publication.

## Recommendation

First establish trustworthy real-data baselines and an inexpensive usable resolver. Then test the original hypothesis that detectors, dictionaries and literature can improve one another. Only scale the variants that earn their place through held-out evidence. Preserve the three original outputs: an improved extraction method, a tagged literature corpus and an expanded dictionary.

The framework is substantial and currently passes its checks: 170 tests and 95.72% coverage. The next work should focus on real inputs, scientific validity and empirical outcomes, rather than another general framework rewrite. The [state audit](project-state-audit.md) records the evidence, limitations and specific code risks.

The user has supplied the 2024 frequency resource and has substantial work CPU/GPU resources. Use local CPU and small optional GPU pilots first, then export pinned environments, input manifests and resumable runs to work infrastructure. A native Windows compiler installation is not the first prerequisite: existing Ubuntu WSL2 already exposes g++ and make. The user has now supplied sibling NCBITextLib sources; T018 uses that copy. Windows invokes the Linux execution path through wsl.exe, with Linux paths and a Linux Python environment.

## Scope and definitions of completion

The primary scientific task is **document-local SF/LF definition extraction** from biomedical abstracts and full text, including tables, captions and abbreviation lists represented in text/XML. Article-wide mention linking is a distinct downstream step. Undefined-acronym sense disambiguation is outside this plan.

There are three useful stopping points:

1. **Operational research platform:** audited real corpora, real Schwartz–Hearst/Ab3P/PLODv2 runs, comparable task-appropriate metrics and a reproducible contemporary pilot workflow.
2. **Useful resolver release candidate:** measured transparent fusion or the strongest single baseline, difficult-structure support where justified, a lightweight learned alternative, and traceable article mention linking.
3. **Full original project:** a controlled, evaluated denoising loop; a substantial, explicitly sized tagged literature snapshot; a provenance-rich expanded dictionary; and a validated reusable package with downstream evidence.

Completion of engineering does not guarantee a positive research finding. A well-supported no-gain result is a valid campaign outcome. It would justify retaining the strongest baseline and releasing honestly labeled resources, but not claiming that abbreviation resolution has been solved.

Image-only figure/table text is a stated coverage limit. T027 measures that gap. If it materially affects the target literature, add a separate bounded OCR investigation with image coordinates and quality assessment; do not silently call caption parsing complete figure understanding.

## Step-by-step milestones

### A Make the existing platform scientifically usable

Implement T017–T022. Reproduce the environment, build real Ab3P, audit corpus semantics, make executable/resource identity reliable, use verified occurrence offsets, and run scored real baselines.

The high-priority repairs are concrete: historical BioC fallback pairing/text reconstruction, Ab3P resource lookup and cache identity, and ambiguous text-only span mapping. Preserve current named scientific policies while making source-specific choices explicit.

**Exit evidence:** real source-to-canonical audit, upstream Ab3P conformance, matching baseline runs with complete provenance, cold/warm cache equivalence and a fresh-environment replay. A synthetic fixture cannot satisfy this milestone.

### B Add complementary evidence and contemporary evaluation

Implement T023–T030, T046, the BioADI feasibility/integration branch T048, and the selection-design portion of T047. T046 explicitly acquires external dictionaries, starting with ADAM and incorporating further user suggestions through the [resource register](resource-acquisition-register.md). All 41 supplied CSV entries are retained in the [resource catalog](resource-catalog.md). ALLIE bulk listings and Acromine documentation are reachable; T048 checks the reachable BioADI JAR before any resolver claim. T047 selects the large-scale document population separately from T029 evaluation sampling. Integrate PLODv2 detection and pairing as distinct stages, obtain a bounded literature snapshot, preserve PubMed/BioC/JATS source structure, ingest the supplied frequency file and create a reproducible sampling/annotation pilot.

The resource has 2,342,940 SF keys and 12,473,609 decoded SF/LF variants. Its integer counts lack per-article links and explicit units. Preserve raw variants and unknown provenance fields. Build occurrence links from the literature before attempting article-coverage selection.

**Exit evidence:** real PLOD spans and paired outputs; traceable prose/table/caption text; a queried real resource; frozen sampling manifests and a reviewed or explicitly provisional annotation pilot. An aggregate-only resource must never supply invented document frequencies.

### C Measure complementarity and deliver simple fusion

Implement T031–T032. Run historical comparisons as soon as T022/T024 exist; do not wait for new annotation to discover obvious implementation failures. Add contemporary results when T030 becomes ready.

Measure unique successes/errors, detection versus pairing loss, exact pair/span metrics, union headroom, uncertainty and runtime. Keep population-oriented sampling separate from deliberately difficult challenge cases. Select a simple hybrid on development data only.

**Exit evidence:** reproducible comparison and a transparent resolver recommendation. The best single baseline remains a valid recommendation if fusion does not help.

### D Test the original iterative-learning idea

Implement T033–T039. Expand structural and lexical candidates; record correlated noisy evidence; induce bounded patterns; build explicit gold/silver training data; train a CPU-oriented scorer; and run a controlled iteration loop.

Reuse the existing candidates, features, scorers and registry contracts. Start with a named logistic-regression research baseline and deterministic evidence rules, not a bespoke large model. Give new evidence, dictionaries, patterns and models separate immutable identities.

**Exit evidence:** a traceable two-iteration pilot with abstention, independent-support checks, rollback and stopping limits. It must demonstrate the mechanism without using its own predictions as gold.

### E Validate the hypothesis and produce resources at work scale

Implement T040–T042, finalizing T047 corpus membership and volume before T042. T041's resumability work can start once milestone A is operational, but large runs wait for measured quality and cost. Freeze a campaign protocol, run ablations on development data, choose one candidate, then confirm on a protected final evaluation set.

Measure quality of the induced dictionary and silver labels as well as resolver accuracy. Expand from a bounded local run to an explicitly sized work-host snapshot using content-addressed shards and failure accounting.

**Exit evidence:** honest research conclusion, measured throughput/memory/storage, completed tagged snapshot, reconciled dictionary counts, independent quality audit and artifact cards. A small pilot is not labeled a substantial corpus.

### F Demonstrate downstream utility and package the result

Implement T043–T045. Mention propagation can be developed after T026/T032, before the whole research loop finishes. Freeze the rest of the downstream pipeline while comparing abbreviation handling.

**Exit evidence:** usable library/CLI interfaces, a real downstream impact report, supported-environment installation checks and a local release package. If downstream data remain unavailable, integration tooling can be complete while the impact claim remains unvalidated.

## Execution order and task map

Retain the existing task numbers; execute T046 after T028 and before T034, and design T047 after T029, finalizing it before T042. Other tasks follow the original sequence subject to dependencies. T048 runs after T022 and contributes additional comparison results if viable. The added identifiers are not end-of-project work. Dependencies identify safe alternative ordering: after T017, corpus audit and the Ab3P build are independent; PLOD detection does not need the whole contemporary benchmark; acquisition/resource work does not need fusion; historical comparison does not wait for annotation; scaling mechanics and mention integration may be prepared before research conclusions. This describes scheduling flexibility, not authorization to spawn agents or execute unassigned tasks.

Assign one bounded task at a time to Luna. Each file includes prerequisites, code/document anchors, implementation steps, acceptance criteria, meaningful checks, scope exclusions and asset blockers. Read the [Luna execution guide](tasks/LUNA_EXECUTION_GUIDE.md).

| Task | Outcome | Hard new prerequisites | Milestone |
| --- | --- | --- | --- |
| [T017](tasks/T017-reproducible-development-environments.md) | Make development and experiment environments reproducible | Current baseline | A |
| [T018](tasks/T018-build-and-verify-real-ab3p.md) | Build and verify real Ab3P in the existing Ubuntu environment | T017 | A |
| [T019](tasks/T019-audit-and-repair-corpus-semantics.md) | Audit historical corpus semantics and prevent silent annotation changes | T017 | A |
| [T020](tasks/T020-ab3p-runtime-and-cache-identity.md) | Make Ab3P resource lookup and cache identity reliable | T018 | A |
| [T021](tasks/T021-ab3p-native-offset-adapter.md) | Use verified Ab3P offsets for canonical span mapping | T020 | A |
| [T022](tasks/T022-real-baseline-smoke-benchmarks.md) | Run reproducible real-data baseline benchmarks | T019, T021 | A |
| [T023](tasks/T023-plodv2-span-detection.md) | Integrate PLODv2 as a reproducible span detector | T017, T019 | B |
| [T024](tasks/T024-plodv2-pairing-resolver.md) | Add explicit PLODv2 pairing strategies and resolver integration | T023 | B |
| [T025](tasks/T025-literature-acquisition-manifests.md) | Acquire bounded literature snapshots with source manifests | T017 | B |
| [T026](tasks/T026-pubmed-bioc-source-parsing.md) | Parse local PubMed and BioC articles with traceable text | T025 | B |
| [T027](tasks/T027-jats-tables-captions-and-definition-lists.md) | Preserve full-text tables captions and definition lists | T026 | B |
| [T028](tasks/T028-lexical-resource-ingestion.md) | Build a provenance-preserving abbreviation resource layer | T017 | B |
| [T029](tasks/T029-sampling-and-leakage-controls.md) | Define contemporary sampling and article-level data separation | T019, T026, T027 | B |
| [T030](tasks/T030-annotation-pilot-and-adjudication.md) | Create an auditable contemporary annotation pilot | T029 | B |
| [T031](tasks/T031-comparative-benchmark-and-oracle-analysis.md) | Measure resolver complementarity and uncertainty | T022, T024 | C |
| [T032](tasks/T032-transparent-hybrid-resolver.md) | Implement an evidence-driven transparent hybrid | T031 | C |
| [T033](tasks/T033-structural-candidate-generators.md) | Generate candidates for difficult prose and full-text structures | T027, T031 | D |
| [T034](tasks/T034-lexical-candidates-and-evidence-features.md) | Use dictionaries and terminologies as local candidate evidence | T028, T029, T033, T046 | D |
| [T035](tasks/T035-weak-evidence-ledger-and-silver-labels.md) | Represent noisy evidence and derive versioned silver labels | T032, T034 | D |
| [T036](tasks/T036-contextual-pattern-induction.md) | Induce and validate reusable contextual patterns | T035 | D |
| [T037](tasks/T037-training-dataset-materialization.md) | Build leakage-safe candidate training datasets | T030, T035, T036 | D |
| [T038](tasks/T038-lightweight-scorer-training.md) | Train and evaluate a lightweight candidate scorer | T037 | D |
| [T039](tasks/T039-controlled-iteration-controller.md) | Implement bounded evidence and model iteration | T036, T038 | D |
| [T040](tasks/T040-research-validation-and-ablation-campaign.md) | Test the denoising hypothesis and select the release candidate | T030, T031, T039 | E |
| [T041](tasks/T041-resumable-bounded-corpus-processing.md) | Make corpus processing resumable and bounded in memory | T022, T025 | E |
| [T042](tasks/T042-tagged-corpus-and-dictionary-build.md) | Build the tagged literature corpus and expanded dictionary | T028, T040, T041, T047 | E |
| [T043](tasks/T043-document-local-mention-propagation.md) | Link abbreviation mentions to local definitions | T026, T032 | F |
| [T044](tasks/T044-downstream-impact-evaluation.md) | Measure impact on the biomedical NLP pipeline | T040, T043 | F |
| [T045](tasks/T045-release-and-reproducibility-package.md) | Package the resolver and research resources for reuse | T040, T042, T044, T048 | F |
| [T046](tasks/T046-external-dictionary-acquisition.md) | Acquire and audit external abbreviation dictionaries | T028 | B |
| [T047](tasks/T047-large-scale-corpus-selection.md) | Select and freeze the large-scale literature corpus | T025, T029 | B/E |
| [T048](tasks/T048-bioadi-runtime-and-resolver.md) | Verify BioADI software and integrate if viable | T017, T019, T022 | B/C |

Some tasks also have real-data or evidence prerequisites stated in their files. For example, T031 can finish a historical comparison before T030, but its contemporary extension needs T030. T041 can prepare infrastructure early; T042 cannot claim scientific improvement before T040.

## Choosing the large-scale documents

[T047](tasks/T047-large-scale-corpus-selection.md) makes this a concrete scientific and implementation task. T025 fetches sources, T029 protects evaluation partitions, T047 selects the large-scale population, T041 executes bounded shards, and T042 creates the tagged outputs.

The selector will compare processing all eligible documents with representative stratified sampling and a broad pool plus a separately labeled enriched pool. It will specify years/cutoff, languages, publication types, abstracts versus full text, availability/reuse class, article versions and duplicate handling. The discovery/training pool, evaluation set and final tagged release remain distinct roles.

The result is a frozen list of article identifiers/versions, inclusion/exclusion reasons, corpus-role labels and a coverage/cost report. Dictionary frequencies may guide enrichment only after occurrence links exist; documents with no baseline detections remain eligible. Work-scale size is selected from actual frame counts and pilot costs, not an invented target. No final population choice is made by this planning revision.

## Pilot sizes and scale handoff

These are adjustable planning proposals, not approved scientific split definitions or guaranteed budgets:

- Start a real baseline smoke on an explicit, reproducible small subset; use enough cases to include empty outputs, repeated forms and Unicode, rather than selecting only successful detections.
- Use roughly 100–500 unlabeled articles for acquisition, structure and throughput pilots, with smaller batches for expensive model checks.
- Prepare a contemporary annotation proposal around 40 articles, initially balanced between abstracts and full text, plus separately identified difficult structures. Conduct a small diverse independent audit before deciding how much to expand. This is a pilot for estimating effort and error modes, not a statistically powered production benchmark.
- Run a small fixed number of denoising iterations locally. Work-scale runs use measured articles/hour, bytes/article, RAM/VRAM, failure rate and disk forecasts to set volume and limits.

The work-host handoff should require only an environment recipe, source/resource/model manifests, machine-local path/device settings, a bounded command and a resume location. Do not embed this Windows checkout path into portable scientific configurations. A scheduler-specific integration is unnecessary until the actual work infrastructure is known.

## Scientific decisions and remaining inputs

The plan preserves existing exact_pair/exact_span policies and exposes additional variants explicitly. The following choices need concrete records before dependent scientific claims, not repeated approval of routine programming work:

| Item | Current position | Needed before |
| --- | --- | --- |
| Target task | Local definitions in abstracts and full text; mention linking evaluated separately | Sampling protocol documents actual production mix |
| Frequency data | Supplied gzip JSON; structure and counts inspected | T028 needs count meaning and extraction provenance when available; unknown fields are allowed |
| Literature source collection | No text collection location supplied | T025 acquires a pilot; T047 chooses the work-scale population and frozen manifest before T042 |
| External dictionaries and software | All 41 CSV references cataloged, including reachable BioADI artifact and ALLIE listings | T046 acquires dictionaries; T048 assesses BioADI software; other systems need explicit follow-up scope |
| Annotation effort | Budget/reviewer availability unspecified | T030 gold certification and T040 contemporary accuracy claims |
| Precision tradeoff | No numeric tolerance invented | Development threshold selection and candidate promotion in T032/T038/T040 |
| Final splits and cutoff | Mechanisms planned; no scientific split chosen | T029 manifests and campaign freeze; linked abstract/full text stay together |
| Work compute | Substantial CPU/GPU available; pilots preferred now | T041/T042 need actual limits, storage paths and supported environment |
| Downstream evaluation | Interface, frozen data and objective absent | T044 impact validation |
| Distribution | Local build and review first | Source/model/data notices and explicit publication action in T045 |

For minimal scientist effort, agents should assemble small review packets containing the source text, alternatives, provenance and exact decision required. An unresolved label should remain unresolved rather than be converted into fabricated certainty. If expert review is unavailable, continue engineering and clearly label agent-assisted data as provisional/silver.

## Research safeguards that must survive implementation

- Detecting SF and LF spans is not the same as identifying their relation. Preserve unpaired predictions and use corpus-appropriate metrics.
- Gold relation ambiguity, repeated definitions, overlap and duplicate policies cannot be chosen for benchmark convenience.
- A contemporary sample selected only from Ab3P outputs cannot establish unbiased recall. Keep an independently sampled component and report sampling limitations.
- Article groups, copies and abstract/full-text counterparts cannot cross evaluation boundaries. Aggregate historical lexical resources may have unknown overlap; compare with/without them and disclose it.
- Detector output, dictionaries derived from that detector and later iterations are correlated evidence. Track lineage and count independent sources conservatively.
- Silver labels and induced dictionary entries require independent quality estimates. More entries or teacher agreement alone are not improvement.
- Do not change evaluation or gold after observing final-test errors and still describe it as untouched confirmation.
- A superior combined system is a hypothesis. Predeclare quality constraints, report uncertainty and retain no-gain/negative outcomes.

## Definition of done for the plan itself

The planning deliverable consists of this overview, the source-backed state audit, the Luna execution guide, the updated task index and 32 individual planned task files. Existing task implementations and completion logs remain historical records. No task implementation was started by creating this plan.

Start by assigning [T017](tasks/T017-reproducible-development-environments.md). The detailed baseline path is T017 → T018/T019 → T020 → T021 → T022; then build the complementary detector and real-literature evidence without waiting for an elaborate ensemble.

