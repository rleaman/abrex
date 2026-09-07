# T028 Build a provenance-preserving abbreviation resource layer

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Query observed SF/LF variants, counts and provenance from the 2024 list or other supplied dictionaries without treating them as gold.

## Dependencies and reading

[T017](T017-reproducible-development-environments.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: handoff/idea.txt; src/abrex/registry/core.py; src/abrex/domain/models.py; docs/features.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Define typed source adapters and a resource query protocol. First support streaming gzip JSON shaped as {SF: {LF: count}} from handoff/abbr_frequency_2024.json.gz, plus local TSV/JSONL; use a deterministic SQLite-backed implementation and preserve raw forms, normalization policy and source hash.
2. Import the supplied 2024 frequency file using bounded-memory iteration; it is about 133.6 MB compressed. Its inspected structure provides aggregate SF/LF counts, without article links. Keep count units explicitly unknown until the extraction provenance is supplied; do not call these document counts.
3. Expose exact-variant lookup, ambiguity, count summaries and source filtering. Do not invent article IDs, document frequency or corpus prevalence from aggregate counts.
4. Allow local terminology/dictionary exports via the same interface, preserving source concept IDs and senses. Produce a resource audit with malformed/merged/unknown-count diagnostics. Actual external-source discovery, acquisition and format-specific ingestion are assigned to [T046](T046-external-dictionary-acquisition.md), beginning with ADAM; a generic importer does not complete that work.

## Acceptance criteria

- Queries return raw variants, declared normalized keys, source lineage and clearly defined counts reproducibly.
- An aggregate-only fixture cannot answer document-level queries as if article links existed; unknown values remain unknown.
- Resources have content identities suitable for cache keys and downstream split/leakage checks; changes invalidate dependent artifacts.

## Verification

Count reconciliation, normalization collision and multi-source provenance fixtures; SQLite repeatability; registry contract and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No automatic UMLS acquisition, forced LF collapse, or global-sense fallback. Resources derived from Ab3P retain that teacher identity and are not independent confirmation.

## Inputs and possible blockers

The user supplied handoff/abbr_frequency_2024.json.gz. Its extraction run identity, count unit, document/year inclusion and duplicate handling still need provenance; absent fields must remain unknown. Substantial work CPU/GPU resources are available later, but first validate a local pilot.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T028-lexical-resource-ingestion.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

