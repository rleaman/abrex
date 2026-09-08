# T027 Preserve full-text tables captions and definition lists

Status: Complete for JATS structural preservation and bounded real-source
validation; OCR and scientific table-pair interpretation remain out of scope.
Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Represent the full-text structures central to the original idea instead of flattening away their abbreviation evidence.

## Dependencies and reading

[T026](T026-pubmed-bioc-source-parsing.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/literature/models.py; src/abrex/literature/segmenters.py; src/abrex/literature/mapping.py; handoff/idea.txt.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Add a local JATS reader that preserves sections, captions, table headers/rows/cells, table footnotes and abbreviation/definition lists with stable source element paths and ordering.
2. Create small format-neutral structural value objects or metadata only where necessary; write an ADR and versioned serialization/migration if the Article contract changes.
3. Define canonical text and mapping policies for inline markup, superscripts/subscripts, nested tables, row/column spans, repeated cells and joins. Retain structure alongside text for later candidate generators.
4. Identify image-only figures/tables as unsupported assets with counts and source references. Caption extraction must not be described as reading figure pixels.

## Acceptance criteria

- Synthetic and real small JATS examples preserve table SF/LF columns, caption definitions and definition-list membership through parsing and output.
- Canonical offsets map back to the correct source element/cell; repeated text is distinguishable.
- Unsupported structures and image-only content are visible in coverage diagnostics; no cross-cell pair is invented by flattening.

## Verification

JATS mixed-content and row/colspan fixtures, table/caption provenance round trip, literature contract and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No OCR in the core milestone and no table-pair acceptance algorithm here. If image-only content materially limits coverage, propose a bounded OCR follow-up with a separate coordinate/artifact contract.

## Inputs and possible blockers

Permitted JATS full text from T025. Source documents containing useful tables/captions are needed for live verification.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T027-jats-tables-captions-and-definition-lists.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
