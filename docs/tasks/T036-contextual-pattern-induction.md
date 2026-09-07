# T036 Induce and validate reusable contextual patterns

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: D.

## Outcome

Discover new patterns from supported literature occurrences and test whether they generalize beyond their seed pairs.

## Dependencies and reading

[T035](T035-weak-evidence-ledger-and-silver-labels.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/candidates/generators.py; src/abrex/registry/core.py; handoff/idea.txt; docs/scientific-contracts.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Extract deterministic context templates around SF/LF occurrences, including punctuation, direction and structural unit labels. Separate literal pair strings from generalizable context features.
2. Propose a bounded pattern language with safe matching and explicit limits rather than arbitrary generated executable code or unrestricted regex.
3. Rank candidates by distinct-document and distinct-pair support, contradiction rates and source diversity. Reserve discovery and development-validation groups; require evidence beyond repeated mentions in one article.
4. Persist proposed, rejected and promoted rule artifacts with versions, seed/evidence lineage and measured precision/coverage. Expose promoted rules through the existing generator interface.

## Acceptance criteria

- A known synthetic context pattern can be recovered without memorizing literal SF/LF values; unsupported broad rules are rejected.
- Validation includes pairs/documents absent from discovery, with article group separation and full error examples.
- Pattern execution is bounded and reproducible; each promotion has evidence and can be rolled back.

## Verification

Template extraction and unsafe-pattern rejection, distinct-support accounting, held-out-pattern validation and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No automatic promotion based only on self-generated support. Thresholds are explicit development settings; the final holdout cannot select patterns.

## Inputs and possible blockers

T035 evidence corpus with enough diverse supported occurrences. If support is inadequate, report insufficient evidence rather than inventing patterns.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T036-contextual-pattern-induction.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

