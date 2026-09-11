# T055 Deliver the assisted audit review interface

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T053 packet; T054 supplement contract.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Extend the existing local reviewer rather than replace its stack. Read the applicable frontend testing/debugging skill; use a new-app skill only if genuinely building a new app. Backend endpoints remain thin adapters.
2. Show article title, source type, case progress and a clearly bounded “Passage to review.” Preserve paragraph breaks. Context is collapsed initially and visually distinct. Place source links nearby; hide offsets, hashes, parser paths and method diagnostics under “Technical details.”
3. Use a readable passage-and-decision layout at desktop width and a stacked layout at narrow width. Each relation card shows the original short form/long form and existing status as read-only history, the proposed new decision, and a plain-language reason for review.
4. Provide explicit buttons “Supported,” “Unsupported,” and “Not sure”; no default acceptance. Ask relation kind, evidence structure, source error and required context with brief help and an uncertainty option. Show “Assisted review” persistently. Method identity may be revealed separately, but hiding it does not make annotations independent.
5. Make text selection functional: select in the passage, then “Use as short form” or “Add evidence fragment.” Show removable fragments in source order with exact text. Support repeated identical strings by position; never locate a selection by first string match. Reconstructed interpretation is a separate text field labeled “Interpretation — not a quotation.”
6. Support adding an overlooked relation, editing a new decision, retaining alternatives and marking a proposed relation unsupported without deleting it. For multi-anchor cases, allow separate relations sharing evidence; do not force a comma-separated list into one short form.
7. Require a separate passage question: “Have you searched this whole passage for additional definitions?” with “Searched,” “Not yet,” and “Uncertain.” Pair decisions alone must not mark the case complete.
8. Provide previous/next, filters for pending/uncertain/changed, counts and a case list. Save before navigation; if save fails, retain edits and explain the failure. Display durable save confirmation, unsaved state, JSON backup/import and packet mismatch errors. No bulk “accept all.”
9. Support keyboard navigation, visible focus, labeled controls, readable contrast and zoom. Escape article markup. Do not create a hosted service, accounts, collaboration system or image annotation tools.
10. Perform actual browser tests: load a real case; reject the 2A proposal; add a relation; select two evidence fragments; annotate repeated text; mark uncertainty; save, navigate, reload, export/import and compare state. Use a disposable QA state, not the scientific review file. Exercise supplementary Unicode and a narrow viewport. Verify the original frozen bundle remains byte-identical.

## Acceptance, deliverables and stopping point

Deliver an opened, usable local reviewer with exact launch command, packet/output locations and a brief illustrated user guide. Record browser actions and outcomes, not merely HTTP/API tests. If browser interaction is unavailable, report frontend acceptance pending and do not call the task user-ready. Run persistence/selection regression tests and the fast gate. Stop before user annotation.

