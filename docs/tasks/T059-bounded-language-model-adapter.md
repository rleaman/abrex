# T059 Prepare one evidence-grounded language-model extraction baseline

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T054 contract; T057 required before final prompt freeze and real challenge run.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Use one configured model and existing permitted local/runtime access. Record exact model/version and inference settings. Do not assume a subscription exposes an API, invent credentials, purchase access or send scientific packets to a new external service without an authorized destination. If access is absent, deliver validated import/export jobs and document the one missing prerequisite.
2. Implement a narrow registry-backed adapter or worker boundary using the existing resolver interfaces; do not build a general model platform. Validate typed output and keep raw output plus diagnostics.
3. Prompt for relations grounded only in supplied text, with quoted evidence, occurrence identification, optional reconstruction and abstention. Do not supply T052 answers, historical reviewer notes, expected counts or other detector predictions. Freeze one development prompt; no prompt search in this task.
4. Resolve quoted evidence to exact positions only when unambiguous; require explicit occurrence disambiguation otherwise. Reject fabricated quotations/offsets and count failures. Preserve multi-fragment evidence in the supplement; pass only eligible exact pairs to the strict resolver view.
5. Configure maximum input size, output tokens, timeouts, retries and total run/token/cost limits. A real run requires concrete limits and an available authorized model route. Record latency, consumption, failures, prompt identity and cache identity. Never log credentials.
6. Use synthetic fixtures for schema errors, repeated strings, unsupported inference and abstention. Run only a tiny smoke on development text when access permits. Claims about quality belong to later tasks.

## Acceptance, deliverables and stopping point

Deliver prompt/config, adapter or reproducible offline job format, validators and actual smoke status. Test malformed/truncated output, ambiguous quoting, Unicode and budget exhaustion. A hand-written fixture is never labeled a real model result. No training, teacher-generated gold, network setup campaign or evaluation-set prompt tuning.

