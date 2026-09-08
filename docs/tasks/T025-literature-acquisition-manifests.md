# T025 Acquire bounded literature snapshots with source manifests

Status: Complete for bounded PubMed EFetch acquisition, manifest/replay
engineering and the two-record live pilot; broader corpus selection and
scientific reuse remain pending. Assigned implementer: GPT-5.6 Luna. Milestone: B.

## Outcome

Obtain a small reproducible PubMed/PMC text collection through existing local files or approved source interfaces. Later bulk acquisition consumes the selected identifier manifest from [T047](T047-large-scale-corpus-selection.md); acquisition itself does not decide the scientific corpus population.

## Dependencies and reading

[T017](T017-reproducible-development-environments.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: src/abrex/tools/download_datasets.py; src/abrex/literature/io.py; docs/literature-integration.md; docs/project-completion-plan.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Define typed acquisition manifests with explicit identifiers/query snapshot, source endpoint, retrieval timestamp, content hash, version, access/license metadata and intended use.
2. Prefer existing user data. Add one narrow NCBI source connector sufficient for a small pilot, with retries, rate limits, pagination, resumability and missing/retracted/updated article accounting.
3. Keep immutable raw responses separate from canonical parsing. Store credentials outside manifests and retain only necessary nonsecret endpoint parameters.
4. Support offline replay of recorded responses and a bounded dry run estimating document count, bytes and requests. Pin a completed search's returned identifiers rather than relying on a mutable query.

## Acceptance criteria

- A fixed small identifier list yields verified raw files and a manifest; rerun reuses unchanged data.
- Missing/inaccessible records and partial downloads are counted and recoverable; no full-corpus download begins by default.
- Offline tests make no network requests, and the chosen endpoint's current usage requirements are documented.

## Verification

Mocked pagination/retry/interruption tests, manifest/hash validation, a small authorized live acquisition, fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

Use a currently supported NCBI automated retrieval service and per-article reuse metadata. No arbitrary PMC page scraping or assumption that all accessible articles may be redistributed.

## Inputs and possible blockers

No local literature text collection location has been supplied. Start with a bounded public/local acquisition pilot; user has substantial work CPU/GPU resources for later scale.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T025-literature-acquisition-manifests.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
