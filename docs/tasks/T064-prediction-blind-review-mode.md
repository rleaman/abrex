# T064 Add a genuinely prediction-blind annotation mode

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T054/T055 reviewer; T057 guidelines. Fixture work can precede T063.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Add an explicit separate blind mode to the existing reviewer. The initial packet, HTML, browser state, API responses, exports and logs visible to the annotator must contain no predictions, method identities, confidence, proposed spans, error categories or T052 answers. Hiding controls with CSS is insufficient.
2. Start with an empty relation list and the bounded source passage. Preserve title/source/context presentation and all selection/edit/multi-fragment/uncertainty controls from T055. Instructions say to find every in-scope definition; do not highlight abbreviation-looking text.
3. Provide “Add relation,” “Save draft,” and an explicit passage-search completion question. A zero-relation completed case requires “Searched this passage; no in-scope definition found.” Empty unreviewed cases must remain incomplete.
4. Support pause/resume, progress, keyboard access, durable save status and JSON backup/import. Do not include a reveal-predictions button during annotation. If broader context is allowed, expose the same context policy to the evaluated methods.
5. Provide an explicit lock/export action for completed annotation, preserving an immutable state hash and exposure status. Incomplete or uncertain items require honest accounting, not coerced decisions. Any later correction creates a new version and records whether predictions were already exposed.
6. Test actual browser flows with disposable synthetic and development fixtures only; do not use unseen evaluation articles for UI QA. Add a relation from scratch, save/reload, complete a true empty case, leave an uncertain case, import/export, and lock.
7. Inspect served packet/API/browser payloads to prove absence of prediction data. Test that assisted packets cannot be opened accidentally as blind packets and lock state is enforced server-side. Verify Unicode/repeated-text selection and narrow viewport.

## Acceptance, deliverables and stopping point

Deliver tested blind mode, guide and launcher. Browser QA and payload isolation tests are mandatory; HTTP success alone is insufficient. Existing assisted mode continues to work. No new app/hosting, prediction generation, annotation or automatic gold certification. User-ready status requires actual interaction tests and durable round trip.

