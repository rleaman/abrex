# T019 Audit historical corpus semantics and prevent silent annotation changes

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: A.

## Outcome

Make every historical benchmark's text, relations, scoreability and source transformations explicit before accepting baseline scores.

## Dependencies and reading

[T017](T017-reproducible-development-environments.md)

Read the [CSV resource catalog](../resource-catalog.md) to reconcile historical corpus references, then [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/corpora/adapters/historical.py; src/abrex/corpora/registry.py; configs/corpora/; docs/corpus-adapters.md; docs/evaluation.md; docs/project-state-audit.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Create a corpus inventory with source version/hash, annotation unit, relation availability, coordinate convention, official split, licensing/source status and eligible metric. Restore available raw sources through existing acquisition/build paths; report unavailable variants.
2. Add regression cases for BioC order-based fallback pairing, unequal SF/LF counts, dangling relations, multiple locations, duplicate IDs and unpaired entities. Replace undocumented inference/loss with explicit source-specific policies and counted diagnostics.
3. Audit BioC JSON annotation-text overlay into document text. Preserve source text by default; any justified repair needs a named transformation, mapping/provenance and a new fingerprint. Compare XML/JSON semantics on equivalent fixtures.
4. Check SDU AI/AE independent spans and SDU AD text-only expansions. Keep their tasks distinct from local pair extraction. Correct stale BADREX references without recreating unavailable datasets.
5. Produce a small source-to-canonical inspection report and update scientific contracts with implemented policy names; unresolved source ambiguities remain explicit.

## Acceptance criteria

- No source annotation disappears silently; all lost, partial, repaired or ambiguous cases are reconciled in counts.
- Independent spans are never paired by list order unless a documented source contract explicitly supports a named variant.
- Each intended benchmark has a documented eligible metric; zero scoreable pairs cannot masquerade as successful pair evaluation.
- At least one real paired corpus is audited and built; raw/processed counts and excluded records are documented.

## Verification

Focused historical adapter/config and canonical artifact tests, equivalent XML/JSON fixture checks, real-source audit, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Keep current exact_pair and exact_span definitions intact. Do not manufacture LF spans for AD, mix reconstructed pair-only text into a natural-text benchmark, or silently replace original corpus variants.

## Inputs and possible blockers

No data/ directory existed during planning. Unavailable sources must be recorded individually; they do not justify blocking every available corpus.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T019-audit-and-repair-corpus-semantics.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

