# T042 Build the tagged literature corpus and expanded dictionary

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: E.

## Outcome

Deliver the first two outputs of the original idea as versioned research resources with honest quality and coverage limits.

## Dependencies and reading

[T028](T028-lexical-resource-ingestion.md), [T040](T040-research-validation-and-ablation-campaign.md), [T041](T041-resumable-bounded-corpus-processing.md), [T047](T047-large-scale-corpus-selection.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: handoff/idea.txt; T028 resource documentation; T040 research report; T041 run manifest format.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Use the frozen T040 resolver on the concrete document/version manifest selected in T047, starting with a bounded pilot and expanding only within the recorded resource limits. Verify source-frame identity, article-role exclusions and the T041 cost estimate before the work-scale run; do not choose corpus membership implicitly during processing.
2. Export tagged corpus shards with canonical/source spans, article/section/structure IDs, method/model/resource hashes, confidence semantics and gold/silver status.
3. Build a derived dictionary with distinct-document and occurrence counts, raw variants, ambiguity, available strata and links to supporting contexts. Deduplicate abstracts/full texts and retries according to named policies.
4. Record corpus coverage, failures, unsupported image-only content, observed noise and population limitations. Audit an independent sample of new/rare dictionary pairs.
5. Create dataset/resource cards, versioned manifests and deterministic rebuild instructions; separate redistributable content from identifier-only or local-only exports.

## Acceptance criteria

- Corpus counts reconcile with shard manifests, and dictionary counts reconcile with the underlying distinct supporting records.
- Every exported pair is traceable to source evidence; counts are labeled observed-snapshot counts rather than universal biomedical frequency.
- Published-size targets are explicit and actually achieved before claiming substantial literature coverage; a pilot is labeled a pilot.

## Verification

End-to-end count reconciliation, duplicate/version and privacy/license-filter fixtures, sample provenance reconstruction, full quality gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Resource creation does not authorize external publication. A negative T040 result may justify a baseline-tagged corpus, but it must not be called an improved system.

## Inputs and possible blockers

User has substantial CPU/GPU resources at work. First estimate per-document cost with T041, then select a work-host snapshot size, storage location and limits. The required source text collection and per-source reuse permissions remain to be identified.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T042-tagged-corpus-and-dictionary-build.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

