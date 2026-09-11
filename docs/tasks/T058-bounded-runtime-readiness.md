# T058 Verify existing baseline runtimes within a repair budget

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T053 inputs; can proceed before T056.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Inspect current S&H, native-offset Ab3P and PLODv2 runtime configs, historical T031 evidence and T051 failures. Verify current executable/model/import origins; historical success is not proof of current availability.
2. Use existing local resources and documented environments first. Test a tiny fixed input containing Unicode, repeated forms and an empty result. Preserve PLOD independent span outputs and pairing outputs separately.
3. Set and record a repair budget before work: proposed ceiling two hours total runtime troubleshooting, at most one bounded repair attempt per optional method, no bulk downloads or new system installation. If a missing prerequisite requires a separate substantial task, record exact remediation and stop that branch.
4. Write a readiness matrix: available/failed/unavailable, versions, resource hashes, worker command, text coverage/truncation, runtime and failure diagnostics. Verify identical canonical text reaches every available method.
5. Provide reusable YAML and reproduction commands with portable machine-local path overrides and cache identities. Never substitute canned predictions or count failed processing as zero detections.

## Acceptance, deliverables and stopping point

Real S&H smoke is required; each optional method has either actual smoke artifacts or a reproducible missing-prerequisite report. Test orchestration failure accounting and changed-input cache invalidation. Deliver a ready run configuration and bounded follow-up list. Optional-runtime failure does not block unrelated annotation work; it leaves the three-way experiment incomplete.

