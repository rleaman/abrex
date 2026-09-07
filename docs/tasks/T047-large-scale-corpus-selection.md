# T047 Select and freeze the large-scale literature corpus

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: B/E. Added September 7, 2026; design after T029 and finalize before T042.

## Outcome

Choose which documents enter the large-scale discovery/training pool and tagged release corpus, with explicit inclusion rules, a frozen identifier manifest and measured selection bias. This is separate from choosing the small evaluation sample in T029 and fetching files in T025.

## Dependencies and reading

[T025](T025-literature-acquisition-manifests.md), [T029](T029-sampling-and-leakage-controls.md).

Read AGENTS.md, START_HERE_FOR_CODEX.md, [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), handoff/idea.txt, and the T025/T029 source and exclusion manifests. Use T028/T046 resources as optional prioritization evidence, and T041 cost measurements when available.

## Implementation steps

1. Inventory the available PubMed/PMC metadata and work-host collections. Define the eligible document universe explicitly: snapshot/date cutoff, publication years, language, document types, abstract/full-text availability, source/reuse class, article updates/retractions and handling of missing metadata. Keep independent text views within one article group.
2. Produce a reviewable corpus specification with three distinct roles: broad discovery/weak-training pool; an optional enriched pool targeting rare forms, ambiguity, tables and captions; and the final tagged release snapshot. Preserve T029's held-out article groups and counterparts across all discovery/training/induction operations.
3. Compare an eligible-universe census with a representative stratified sample and a broad-plus-enriched design. Report frame counts, years, journals/domains, text types, structure availability, estimated storage/runtime and expected coverage. Choose the practical design using explicit scientific scope and work-resource limits; do not silently equate 'large' with 'all PubMed/PMC'.
4. Implement a YAML-selected deterministic selector with article/version deduplication, recorded seed where sampling occurs, quotas/priorities, eligibility and exclusion reasons. Preserve selection probabilities for representative strata; tag enriched examples so their counts cannot be mistaken for unbiased prevalence.
5. If frequency/coverage selection is used, build or consume article-level SF/LF occurrence links. The aggregate 2024 JSON cannot identify articles. Retain documents where existing detectors find no pairs so the corpus does not exclude novel definition styles by construction.
6. Write a frozen manifest of selected identifiers/versions, source locations and hashes when acquired, role, selection reason, article group and exclusion history. Use it to drive T025 acquisition and T041 shards. Run a small local selection/acquisition pilot, then use measured T041 costs to finalize the work-scale size and limits without changing the protected holdout.

## Acceptance criteria

- A concrete corpus specification and selected identifier manifest exist; 'an approved snapshot' is not left as an undefined input for T042.
- The same source frame/configuration reproduces the same selections; duplicates, unavailable records and exclusions reconcile with total frame counts.
- Discovery/training and derived resources exclude evaluation article groups, including PMID/PMCID and abstract/full-text counterparts. If evaluation articles are later tagged for a final inference-only release, their separate status is explicit and they never feed back into model/resource selection.
- Broad and enriched pools retain distinct labels and denominators. The final document count, time span, selection rationale and work-scale cost limits are recorded before the bulk run.

## Verification

Deterministic selection, quota/census behavior, article-group leakage, missing metadata, source-version changes and count reconciliation tests; a small real metadata-frame pilot; repository fast gate. Validate final volume/cost estimates against T041 measurements before T042 runs.

## Scope and scientific boundary

Do not conflate a training pool, a benchmark and a release corpus. Prepare a concrete selection proposal when corpus inclusion criteria are unresolved, while implementing configurable mechanisms. No bulk retrieval or GPU campaign is implied by choosing identifiers. T029 owns evaluation sampling; T041 owns execution mechanics; T042 owns tagged/resource production.

## Inputs and possible blockers

The user has substantial CPU/GPU resources at work, but text collection paths, desired time range and storage limits remain unspecified. Start with accessible metadata and a small pilot. Final scale selection needs those limits and measured costs, not a guessed document count.

## Deliverables and completion note

Deliver the corpus specification, selector/configuration, source-frame and selected/excluded manifests, tests, coverage/bias report and work-scale size/cost recommendation. Keep large manifests untracked or in the designated artifact store with checked-in fingerprints. Record results in docs/tasks/completed/T047-large-scale-corpus-selection.md before T042 consumes the snapshot.
