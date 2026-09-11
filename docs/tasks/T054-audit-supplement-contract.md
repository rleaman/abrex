# T054 Add a versioned audit supplement contract

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T053 inventory and question sheet.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Inspect existing review models, provenance, persistence and BioC round trips. Design an additive, versioned supplement linked to the immutable T052 packet and annotation-state hashes; retain the ability to load and export the old schema.
2. Implement typed fields for support (supported/unsupported/uncertain/unreviewed), provisional relation kind (abbreviation expansion/other naming or code relation/uncertain), evidence structure (contiguous/shared or discontinuous/uncertain), source-error flag and required context (text alone/document structure/image/uncertain). Keep caption/table scope separate from relation kind. Values describe proposals until T056.
3. Preserve exact anchor spans and an ordered list of exact evidence spans. A separate optional interpreted expansion must be explicitly labeled reconstructed and must not acquire fabricated source coordinates. Preserve one-to-many alternatives, repeated occurrences, source text errors and unresolved mappings.
4. Track per-relation decisions separately from whole-passage search completion. Record reviewer identity, timestamps, revision history, assisted exposure and explicit “searched; none found” versus “not searched.”
5. Validate every span against canonical Unicode text and reject stale packet identities. Use atomic durable saves and explicit errors; old annotations must never be silently upgraded or overwritten.
6. Document the supplement schema with minimal examples for ordinary expansion, discontinuous evidence, unsupported pair and source-error proposal. Do not extend the canonical definition/evaluator to multimodal objects.

## Acceptance, deliverables and stopping point

Round-trip supplement and history exactly; test mismatched identities, Unicode, repeated spans, multi-fragment evidence, concurrent/stale revisions and interrupted-save behavior. Existing T052 interchange regression tests pass. JSON is the authoritative new supplement format; if BioC cannot represent new fields, preserve them losslessly in a tested sidecar or explicitly keep export legacy-only. No UI yet.

