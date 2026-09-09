# Project status review — September 8, 2026

Reviewed checkout: `830ebe6` (`Complete T045 release package`). The tracked tree was clean before this review. This is a status/acceptance audit, not a complete line-by-line code review. No implementation or scientific policy was changed. Live external resolvers were not rerun; their results below are recorded artifact evidence.

## Overall assessment

ABREX has a substantial modular software foundation and real bounded baseline evidence. It has not completed the original research project. There are 49 completion notes for T000–T049, with T042 absent, but many notes explicitly certify only engineering mechanisms or tiny pilots. Counting completion notes as completed research outcomes is misleading.

The original three contributions remain outstanding:

1. Substantial tagged literature: not built (T042).
2. Substantially expanded dictionary with observed frequencies and supporting contexts: not built (T042).
3. Improved extraction: not established (T038–T040). The bounded comparison retains native-offset Ab3P.

## Evidence that exists

- Core domain/configuration/registry, corpus adapters, canonical serialization, evaluation, caching, resolver integration and local release packaging exist.
- Ab3P and PLODv2 have recorded real runtime/comparison evidence. Old notes describing PLOD runtime blockers are superseded by the successful T031 run.
- T031 compares three resolvers on 64 Ab3P-corpus documents with 143 gold pairs. Ab3P precision/recall/F1 are 0.9680/0.8462/0.9030; Schwartz–Hearst F1 is 0.8527; PLODv2 pairing F1 is 0.7790. Gold-assisted union recall is 130/143 (0.9091), not a deployable ensemble result.
- The T032 two-resolver union gains three true positives but four false positives over Ab3P; F1 is 0.9018. It does not establish an improvement.
- T033 structural-prose and T034 bounded lexical additions do not improve candidate recall on that slice. The slice has no JATS structure metadata, so this does not evaluate table extraction.
- Literature acquisition/parsing has bounded real evidence: two PubMed records and one JATS article, alongside fixtures. JATS structure preservation exists; figure pixels/OCR remain unsupported.
- ADAM and ALLIE have bounded acquisition/import evidence, not complete production resource ingestion.

The historical sample explicitly excludes empty-gold documents and comes from one corpus. Its scores cannot establish representative contemporary accuracy, false-positive behavior across ordinary literature, or full-text/table performance.

Sources: `docs/tasks/completed/T022*`, `T025*`, `T027*`, `T031*`–`T034*`, `T046*` and associated `docs/artifacts/` reports.

## Remaining work by task

| Tasks | Delivered | Still required |
| --- | --- | --- |
| T029 / T047 | Deterministic sampling/selection mechanisms; five-record metadata fixtures | Actual literature frame, target years/languages/types, abstract/full-text mix, duplicate/version/reuse rules, protected evaluation groups, pool sizes, frozen identifier/version manifest |
| T030 | Annotation schema, review packets, provenance and four-case provisional pilot | Real contemporary sample; independent review, adjudication and unresolved-label policy; certified gold and frozen development/evaluation partitions |
| T031 | Historical three-resolver smoke comparison and oracle analysis | Contemporary extension after T030; broader historical coverage if desired; structural/error strata on suitable data |
| T033 / T034 | Structural/lexical candidate mechanisms and bounded no-gain results | Real table/definition-list extraction evaluation and useful resource-scale ablations |
| T035 / T036 / T037 | Evidence ledger, literal template induction and label/materialization APIs | Real multi-source evidence builders, independently audited silver labels, held-out rule validation and reproducible training artifacts |
| T038 | Logistic-regression scorer and persistence tests on four synthetic rows | Runnable training workflow over T037 artifacts; gold-only versus silver-assisted experiments; development thresholds, recall ceiling, quality/runtime reports |
| T039 | Metadata stage controller and checkpoint tests | Actual dictionary/pattern/label/model execution integration and stronger lineage, resume and resource-limit enforcement |
| T040 | Summary of existing exploratory results and no-promotion decision | Actual gold/silver and zero/one/multiple-iteration ablations; dictionary/noise audit; frozen final confirmation when suitable data exist |
| T041 | Generic resumable shard processing | Representative throughput, memory/storage/failure measurements on the intended runtime and source mix |
| T042 | Specification; supporting infrastructure elsewhere | Tagged-corpus/dictionary build implementation, count reconciliation, source-context traceability, quality audit, cards and versioned release artifacts |
| T043 / T044 | Mention propagation and downstream comparison interfaces/fixtures | Real mention-linking/false-expansion evidence; actual downstream adapter, frozen data, metric and impact comparison |
| T045 | Local wheel and limited install/CLI smoke | Repair verification gaps; clean separate-environment release validation and eventual resource/research package. Publication remains a separate action |
| T046 / T048 | Bounded dictionary and BioADI feasibility/integration | Optional resource expansion/provenance decisions; BioADI mapping/abstention policy before comparable evaluation |

T048 recorded 51 mapping failures out of 64 documents. Its metrics on the 13 successful documents cannot be compared directly with the full 64-document baseline. This optional resolver should not block the core project.

ADAM's source row/count discrepancy and bulk reuse terms remain recorded issues for expansion. Other cataloged resources are candidates, not automatically mandatory dependencies. BADREX-corrected corpora remain excluded under the settled decision; their absence is not a blocker.

## Engineering findings independent of scientific decisions

### Verification is not release-complete

Fresh checks:

- Default fast gate: formatting/lint/type checks pass; 307 tests pass.
- Default full gate: 311 tests pass, but coverage fails at 52.15%. Coverage includes both installed `env313/Lib/site-packages/abrex` and checkout `src/abrex` copies.
- Full gate repeated with process-local `PYTHONPATH` pointing to `src`: formatting/lint/type checks pass; 311 tests pass; source coverage is **94.18%, below the required 95%**. The gate still fails.

The wheel install has left the development environment testing an installed package by default. Development/source checks and isolated wheel checks need distinct, explicit import environments. The source coverage failure is real after removing the duplicate-copy artifact; 52.15% is not the source's actual coverage.

Evidence: `.artifacts/status-audit-full-gate.txt`. No dependencies or installed package were changed during this review.

### T039 is a controller scaffold, not the research loop

`src/abrex/experiments/iteration.py` accepts preconstructed stage records and supplied development scores. It does not execute evidence/dictionary/pattern/label/model builders. Parent hashes are serialized but not validated as an acyclic dependency graph. Configuration has iteration/document/stage bounds but lacks the specified time/storage bounds. The final checkpoint uses the planned iteration count even if a guard stops the loop earlier, which warrants a regression fix before relying on resume.

These are implementation/verification gaps, not matters requiring the user to choose a corpus.

### T036 needs stronger validation before rule promotion

`src/abrex/patterns.py` counts distinct span-coordinate pairs rather than distinct lexical SF/LF pairs, labels patterns promoted from document/pair support alone, and validates only positive records. Its single test reuses discovery records as validation records. This does not establish held-out generalization, precision or independent support. Article/pair separation, negative evidence, promotion guards and generator integration need acceptance review before a learning campaign.

### T040's report is a static audit rather than an executable campaign

`scripts/build_t040_campaign_report.py` hashes supplied files but hard-codes the reported scores and decision; it does not read their metrics or the YAML protocol. Changing the inputs therefore changes hashes while leaving reported scores unchanged. The existing numbers agree with the recorded small experiments, but the script is not a reliable reusable campaign evaluator. It needs validated input-derived metrics and actual experiment orchestration.

### Recorded artifact versions need refreshing

The T030 provenance and T046 ADAM persistence fixes explicitly say older generated artifacts must be regenerated to contain the new fields. Preserve historical reports, but regenerate and fingerprint current artifacts before downstream use.

## Decisions to discuss

There are two related literature choices, not one: the small independently reviewed evaluation/development sample and the larger discovery/training/tagged-release population. They need compatible article grouping and leakage controls, but different selection purposes.

1. Target population and task mix: contemporary years, sources, abstracts/full text, languages/publication types, and how much tables/captions/definition lists matter. Image-text extraction requires separately scoped work if needed.
2. Review effort: who can independently review a small diverse packet, how much time is available, and how disagreements/unresolved cases are handled. The agent can assemble the packet and propose a protocol; assisted labels alone remain silver.
3. Success criterion: acceptable precision loss for additional recall, and whether the near-term aim is a baseline-tagged resource or evidence for a better resolver. Final thresholds should be chosen before confirmatory evaluation.
4. Work host: supported environment, storage location, CPU/GPU/RAM and run limits. Agents should measure representative pilot costs before proposing a work-scale size.
5. Downstream scope: actual pipeline/data/metric if downstream impact is required now; otherwise keep T044 explicitly deferred.

## Suggested next sequence

1. Separate task status into engineering, real-data validation and scientific outcome. Reopen concrete T036/T038/T039/T040/T045 engineering gaps and fix the source/release verification setup.
2. Prepare a compact literature and annotation proposal with a small independently sampled component and separately reported challenging structures. Ask for decisions on an assembled packet, rather than expecting the user to design the study.
3. Acquire the bounded approved sample, certify labels, freeze article-group partitions and rerun the comparison on relevant contemporary data.
4. Connect the evidence/learning components and run a bounded campaign. Preserve a no-gain outcome if that is what the evidence supports.
5. Measure processing cost and freeze the larger corpus, then implement T042. A baseline-tagged corpus is legitimate if explicitly labeled; it need not wait indefinitely for an improved resolver.
6. Validate downstream impact when the actual inputs exist, then rebuild and verify the final local package/resources.

The central research hypothesis has not been adequately tested; the bounded no-gain results do not establish that it fails. Conversely, a working scaffold and completion notes do not establish that it succeeds.
