# T053 Build the targeted T052 audit inventory

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: Frozen T052 bundle; no new annotations required.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Read the frozen manifest, packet, final annotation state and outcome summary. Verify hashes and reconcile current decisions without counting revision history twice. Produce an inventory of all 60 cases and 105 current decisions.
2. Select every case containing an added pair, corrected suggestion or rejection. Deduplicate at case level while preserving all selection reasons. Add up to eight deterministically sampled cases containing only unchanged accepted suggestions, with article diversity and a recorded seed. Report shortages and selection denominators.
3. Include full reviewed passages, not just selected pairs, so the user can search for further misses. Carry stable case, decision, article-group and source identifiers into a new packet.
4. Flag these as questions, never automatic corrections: `2A → agonist-bound A`; the unrecorded HDL2-apoA-I/HDL4-apoA-I occurrences; shared material and trailing “tensions” in the tcPO2/tcPCO2 passage; ratio components versus whole ratios; the repeated HDL1-PL source typo; VLDL3-C/VLDL4-C one-to-many mapping; D-group versus component mnemonics.
5. Distinguish the recorded `corrected` origin from an actual span/text change. Report additions by article and passage, including the 13 additions concentrated in two lipid passages.
6. Write a concise question sheet and machine-readable inventory under a task-owned artifact directory. Link to the frozen sources; do not copy historical conclusions as adjudicated facts.

## Acceptance, deliverables and stopping point

Counts reconcile; deterministic selection replays identically; all flagged questions trace to source text and current decisions. Test selection, deduplication and history/current separation. Deliver packet, question sheet and reproduction command. No frontend or adjudication in this task.

