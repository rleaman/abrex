# T052 Deliver the pilot review interface and annotation round trip

Status: Authorized; fixtures/interface may proceed if T051 has external delays. Implementer: GPT-5.6 Luna.

## Outcome and dependencies

Let the user review the actual T051 cases through a working local browser interface and recover durable, traceable annotations. Follow [current work](../CURRENT_WORK.md) and inspect the existing T030 annotation models/provenance and report infrastructure. Apply relevant frontend/testing skills for the UI as appropriate; do not substitute a read-only report or raw XML for the interface.

## Implementation

1. Build the deterministic initial packet under the approved 60-case allocation, per-article cap and source-arm balancing rules. Preserve selection category, universe size, seed and reason. Shortages remain explicit. Keep disagreements, agreements, enriched no-detection and uniform no-detection strata separate.
2. No-detection eligibility requires successful complete coverage by all three primary methods and zero accepted definition pairs intersecting the passage. An abbreviation-like regex or unpaired PLOD SF span is a review priority, not a gold annotation. Keep an unbiased control component even if it contains no abbreviations.
3. Provide a small local reviewer with next/previous/filter/progress, readable passage and wider context, accessible highlighted SF/LF alternatives, source links and structural comparison views when available. Hide method identity until revealed while accurately marking suggestions assisted. Escape source content; do not execute article markup.
4. Support accepting/rejecting/marking uncertain, correcting exact SF/LF spans, adding a missed definition, declaring no definition, and notes. Validate edits against the immutable passage/article text. Preserve repeated/nested/alternative definitions and unresolved mappings rather than flattening them away.
5. Persist annotation revisions and save/resume state with explicit JSON download/import backup. Browser storage alone is insufficient. Detect packet/version mismatch instead of attaching saved edits to a different source. Verify a Unicode selection/edit/export/import round trip including supplementary characters (browser UTF-16 versus canonical Unicode character offsets).
6. Export/import BioC XML with explicit SF/LF annotation nodes, relation endpoints/roles, passage/document offsets, statuses and traceable provenance. Sidecars may preserve metadata unsupported by the external tool, with stable reconciliation IDs. Keep predictions separate from human decisions and preserve unreviewed/rejected/uncertain cases.
7. TeamTat is optional. Inspect its documented BioC/preannotation behavior and verify a tiny real import/export if accessible without an account dependency. If untested, describe the XML as BioC interchange with TeamTat compatibility unverified; the working local reviewer must still be delivered. Do not create accounts, invite annotators or publish a site.
8. Produce a compact pilot readout: sources processed, method coverage/failures, disagreements, format problems, throughput/storage and review instructions. Do not report precision/recall from disagreements or count unreviewed cases as negatives. Add analysis of reviewer outcomes only once the user supplies them.

## Acceptance and verification

- Open the actual reviewer and exercise selection, span edit/addition, status change, notes, navigation, save, reload and export/import on at least one real case plus Unicode/structural fixtures. Record actual UI testing; XML schema validation is not UI testing.
- First real packet exists and all cases trace to source snapshots, selection strata and prediction artifacts. Counts reconcile and packet size obeys the budget.
- Canonical annotation provenance round-trips without silently dropping source alternatives or edit history. A model suggestion is never certified independent gold.
- Focused packet/serialization/regression tests, UI checks, canonical fast/full quality gates and diff checks pass.

## Deliverables and handoff

Working local reviewer, actual bounded review packet, BioC XML and JSON interchange, concise user instructions, manifest/report and `completed/T052-pilot-annotation-interface.md` when accepted. Open the result for the user and report exact review launch/file location, counts, method/format limitations and remaining human review. Stop this implementation milestone here. Do not launch the broader T036–T045 research campaign.

Reference: https://www.teamtat.org/ documents BioC upload, preannotation and entity/relation annotation. Actual import fidelity must be checked separately.
