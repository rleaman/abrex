# T046 Acquire and audit external abbreviation dictionaries

Status: Planned. Assigned implementer: GPT-5.6 Luna. Milestone: B. Added September 7, 2026; execute after T028 and before T034, not at the end of the project.

## Outcome

Acquire real external abbreviation resources, beginning with ADAM, and ingest them through T028 with source-specific semantics and reproducible provenance. A generic importer alone does not satisfy this task.

## Dependencies and reading

[T028](T028-lexical-resource-ingestion.md).

Read the [complete CSV resource catalog](../resource-catalog.md), including all original citations, then AGENTS.md, START_HERE_FOR_CODEX.md, [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [resource acquisition register](../resource-acquisition-register.md), [completion plan](../project-completion-plan.md), and handoff/idea.txt. Inspect the existing dataset downloader and T028 resource protocols before adding acquisition code.

## Implementation steps

1. Maintain a source register including ADAM, ALLIE, Acromine, SaRAD, Stanford Biomedical Abbreviation Server, ARGH and AcroMed from the supplied CSV. Preserve both Acromine publications as references to one resource family. Prioritize a usable official ALLIE extract and verified Acromine access alongside ADAM investigation; citations alone do not establish downloadable resources. For each record official landing/download locations, release, domain, extraction method, raw variants, count semantics, context/article links, access terms and possible overlap with other resources. Rank by complementarity and usable access, not size alone.
2. Investigate ADAM's current official bulk access. The user supplied http://abel.lis.illinois.edu/adam.html; the planning browser received a 502 on September 7, 2026. The original publication describes a text-file download, but a historical publication is not proof of current availability. Check official alternate locations or a user-supplied copy; never substitute an unverified mirror silently.
3. Add a typed resource acquisition manifest and resumable, checksum-verifying downloader or local-file import path. Preserve downloaded bytes and notices separately from normalized query artifacts. Reuse existing acquisition infrastructure where appropriate; no interactive site scraping is required merely because a query UI exists.
4. Implement and test the real acquired format through T028. Preserve ADAM's source-provided grouping of morphological variants without applying it indiscriminately to other dictionaries. Unknown count/context fields remain unknown. Record source-family lineage rather than treating dictionaries as independent votes by default.
5. Route software entries to T048 or explicit follow-up tasks and corpus entries to T019/source review; do not ingest a JAR as a dictionary. Ingest at least one actually available external dictionary and reconcile source rows, unique raw pairs, variants, counts, ambiguous entries and dropped/repaired records. Produce a small lookup demonstration and a per-source availability report. Additional suggested resources use the same bounded adapter workflow.

## Acceptance criteria

- At least one real external dictionary, beyond the supplied 2024 list, is acquired and queried reproducibly through T028; fixture-only ingestion is insufficient.
- ADAM is either acquired with verified provenance or explicitly remains unavailable/pending, with attempted official locations and an actionable local-file route. An alternative resource does not count as having acquired ADAM.
- Every source has a pinned artifact identity, access status, count semantics and lineage; no unknown rights or metadata are invented.
- The source audit reconciles all input records and preserves resource-specific variants and senses.

## Verification

Mocked download/retry/hash failures, format-specific parser fixtures, real-source count reconciliation and lookup smoke, T028 registry contract, repository fast gate. Record actual retrieved versions and dates.

## Scope and scientific boundary

Resource acquisition is distinct from T034's scientific use. No local definition is asserted merely because a dictionary contains a pair. No automatic UMLS credential acquisition, contacting maintainers, purchasing data or external redistribution. Add user suggestions to the register even when access remains unresolved.

## Inputs and possible blockers

ADAM's current download endpoint is unverified. User-supplied copies or official alternative sources may resolve access. The 41-row user CSV has been cataloged; ALLIE has a verified official download directory and Acromine has reachable REST documentation, but selected artifact versions, actual API access and source terms still need verification. One unavailable resource must not prevent work on other available resources.

## Deliverables and completion note

Deliver the source register, acquisition configuration, scoped adapters, tests, source audits and documentation. Keep bulk files untracked. Record engineering completion and each source's acquisition status separately in docs/tasks/completed/T046-external-dictionary-acquisition.md; do not claim ADAM success if it remains unavailable.
