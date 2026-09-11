# T060 Run the bounded development comparison and build an output review packet

Owner: **Luna — engineering and preparation**  
Status: Planned; this file does not authorize automatic execution.  
Dependencies: T057 challenge views; T058 readiness; T059 model baseline readiness or explicit unavailable status.

## Execution contract

Read [the milestone plan](../post-t052-next-steps.md), [Luna's guide](LUNA_EXECUTION_GUIDE.md), AGENTS.md and the specific dependency outputs. The plan's common acceptance and scientific safeguards are part of this task. Existing interfaces are starting points, not a requirement to duplicate them.

## Implementation steps

1. Freeze run settings, available methods and input hashes. Run the existing methods and the one language-model baseline on the same complete selected passages, with the same permitted context and recorded coverage. Keep any context differences explicit.
2. Reuse existing experiment orchestration, comparative analysis and prediction storage. Retain original predictions, exact spans, unpaired PLOD detections, timings and failures. No fusion fitting or new candidate generator in this task.
3. Link predictions to adjudicated development relations under the frozen policy. Label provisional matches and mismatches as machine-derived, not new user judgments.
4. Build a bounded assisted review queue for all novel predictions, contested boundaries, unsupported/out-of-scope proposals and unclear mappings. Deduplicate review presentation while retaining every method's contribution and repeated occurrence identity.
5. Reuse T055 cards for output adjudication, with source passage and frozen previous decisions available. Do not present model confidence as correctness. Method labels can be hidden until reveal, but all output-visible review remains assisted.
6. Report exact queue size and estimated review burden. If unexpectedly large, split into resumable batches; do not drop cases or call a sampled queue exhaustive. Do not enlarge the corpus.

## Acceptance, deliverables and stopping point

All methods' successes/failures and outputs reconcile to inputs. Failed passages are not false negatives or clean negatives by default; coverage is explicit. Deliver artifacts, updated reviewer packet, launch command and queue counts. Test joins, duplicate presentation, failure accounting and frozen-input enforcement. Stop for T061 before interpreting unjudged outputs as errors.

