# T060 Run the bounded development comparison and build an output review packet

Owner: **Luna — engineering and preparation**  
Status: Complete — split-question Jev revision, four-way pair comparison, and
PLOD independent-span audit complete; T061 is a separate user task.
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

## October 4 Jev correction

The original Jev policy combined definition validity and orientation in one
three-way Choice. That is retained as historical v1 evidence, but it is not the
current T060 result. The corrected `abrex-candidate-split-v2` policy asks an
independent Noul about the exact pair's validity and a speculative Choice about
orientation in the same request. A new content-addressed cache was populated,
both thresholds were calibrated on the frozen development material, and the
final prediction artifact was replayed cache-only.

The revision did not require rerunning Schwartz–Hearst, Ab3P, or PLODv2 because
their inputs and outputs were unchanged. The revised comparison is
[`T060-development-comparison-split-v2.json`](../artifacts/T060-development-comparison-split-v2.json),
and its 11-passage/33-proposal assisted packet is
[`review-packet-split-v2.json`](../../evidence/T060/review-packet-split-v2.json).

## October 4 PLOD span completion

The independent detector follow-up completed all 20 passages in 89.15 seconds
with no execution errors. The audit retains 275 exact endpoints: 239 short-form
and 36 long-form. Every one of the 72 endpoints used by PLOD pairing occurs in
the detector output; 203 detector-only endpoints remain separately recorded
and are not converted into definition pairs. The audit is embedded in the
corrected comparison artifact and does not reopen completed T057 passage
searches or add user annotation work.

## Acceptance, deliverables and stopping point

All methods' successes/failures and outputs reconcile to inputs. Failed passages are not false negatives or clean negatives by default; coverage is explicit. Deliver artifacts, updated reviewer packet, launch command and queue counts. Test joins, duplicate presentation, failure accounting and frozen-input enforcement. Stop for T061 before interpreting unjudged outputs as errors.

