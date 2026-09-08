# T026 Parse local PubMed and BioC articles with traceable text

Status: Complete for local PubMed XML/BioC parsing, source provenance and
bounded live round-trip scope; broader full-text structure remains pending.
Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Translate actual abstract/BioC source files into the existing Article and canonical document boundaries without losing source identity.

## Dependencies and reading

[T025](T025-literature-acquisition-manifests.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/literature/models.py; src/abrex/literature/segmenters.py; src/abrex/literature/io.py; docs/literature-integration.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Implement registry-backed local readers for the specific PubMed XML and BioC formats acquired in T025, keeping networking outside the readers.
2. Preserve PMID/PMCID, version/hash, title, structured abstract sections, passage identifiers and original coordinate conventions. Define title inclusion, whitespace and join policies explicitly.
3. Retain source-to-canonical mappings for transformed text, including Unicode, XML entities and inline markup. Do not overwrite existing source annotations when adding predictions.
4. Expose a thin conversion CLI and examples that feed the existing ArticleResolutionService; emit diagnostics for unsupported passages, duplicate IDs and malformed source content.

## Acceptance criteria

- At least one actual PubMed abstract and BioC article round trip into source-traceable canonical text and predictions.
- Synthetic fixtures verify nonzero passage offsets, structured abstracts, titles and inline markup without silently changing text.
- The same source/config yields the same canonical fingerprint; changed text or segmentation produces a new identity.

## Verification

Offline parser integration/contract cases, source-span round trip, existing literature regression tests and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No retrieval clients in domain/resolver code; no scientific rule that every title pair is wrong. Structured JATS tables belong to T027.

## Inputs and possible blockers

Small raw examples from T025; only redistribute fixtures when permitted, otherwise use synthetic equivalents and manifests.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T026-pubmed-bioc-source-parsing.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
