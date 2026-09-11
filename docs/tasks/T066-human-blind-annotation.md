# T066 Annotate the fresh passages before seeing predictions

Owner: **USER — scientific lead; not a Luna implementation assignment**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T065 actual prediction-free packet and guide.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Your steps

1. Read the frozen guidelines and annotate all in-scope definitions in each passage from scratch. Search the whole annotatable passage, including passages with no obvious abbreviations.
2. Select exact source evidence. Record shared/discontinuous evidence separately from a reconstructed interpretation; use uncertainty rather than forcing a match.
3. Explicitly mark searched passages with no in-scope definitions. Save drafts when a passage is incomplete. Report interface problems without asking Luna to propose the answers.
4. Do not consult evaluated model outputs or ask the evaluated language model to annotate the test passages. If accidental exposure occurs, record it.
5. Complete any approved independent second-reviewer subset before prediction reveal. Preserve both initial annotations and disagreement/adjudication history. If there is only one reviewer, report that limitation.
6. Save/export and lock the annotation state; return the file location and note unresolved cases. Complete the lock before Luna starts T067.

## Acceptance, deliverables and stopping point

User deliverable: locked prediction-blind annotations with passage completeness and uncertainty recorded. Luna may fix tooling and validate data integrity without interpreting source relations. Independent gold is not automatically claimed; provenance must reflect the actual reviewer and exposure history.

