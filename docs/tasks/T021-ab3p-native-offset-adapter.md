# T021 Use verified Ab3P offsets for canonical span mapping

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: A.

## Outcome

Resolve repeated forms and multiline text without guessing which occurrence an Ab3P pair refers to.

## Dependencies and reading

[T020](T020-ab3p-runtime-and-cache-identity.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: ../Ab3P/lib/Ab3P.h; ../Ab3P/lib/Ab3P.C; ../Ab3P/identify_abbr.C; src/abrex/resolvers/adapters/ab3p.py; tests/unit/test_ab3p.py.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Verify the meaning, initialization and units of AbbrOut.sf_offset and lf_offset against implementation and live examples; the fields exist but their usable semantics must be demonstrated.
2. Add a small versioned offset-emitting frontend around the unchanged upstream library if those offsets are reliable. Preserve upstream line-processing behavior and capture pair strings, precision, strategy when available, line identity and offsets.
3. Translate verified source byte/line offsets into canonical Python character intervals with explicit UTF-8 boundary checks. Account for CRLF, Unicode, repeated mentions and line origins without normalizing input invisibly.
4. Keep legacy text-only parsing as a separately identified replay path with explicit ambiguity errors. Add live-derived golden artifacts alongside the existing synthetic parser fixtures.

## Acceptance criteria

- Two repeated definitions and a later reuse of an SF map to the actual detected positions, not arbitrary string-search matches.
- Unicode prefixes, Greek letters, CRLF/multiline input and reverse-order output either map correctly or produce a specific diagnostic; every emitted span slices to its reported form.
- Detection pairs match the unchanged upstream frontend for equivalent inputs; schema/wrapper identity changes invalidate caches.

## Verification

Live offset conformance, repeated-text regression, UTF-8 boundary and line-offset tests, old-cache parser compatibility, regression suite and fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

If native offsets prove unreliable, document evidence and implement an explicitly specified alternative with retained ambiguity. Never silently pick the nearest occurrence or patch the scientific algorithm.

## Inputs and possible blockers

T018/T020 live installation and permission to compile the task-owned wrapper.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T021-ab3p-native-offset-adapter.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.

