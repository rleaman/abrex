# Current work: CLP transfer and comparative extraction campaign

## Active campaign

The user authorized experiments 1–4 in
[`experiment-campaign-2026-10.md`](experiment-campaign-2026-10.md): complete CLP
transfer, include Ab3P, explain cross-method errors, compare source-grounded
direct extraction with candidate judging, and then prepare one frozen
contemporary comparison. The campaign supersedes historical task boundaries;
it does not authorize downstream experiment 5 or a new scientific-data API
destination without explicit access/budget approval.

## Verified Milestone A delivery

Milestone A is complete as development evidence. The pinned full CLP V5.1
source is commit `323fd4f51aa3c5b54ed30f37dd297b00b49e277e`, archived at
`resources/clp/clp-v5.1-source.zip` with SHA-256
`290a52ad53216de64fca78abff2682057cc77b0d3c3ee698580a8ca9f94df7d7`.
The narrow V2 worker preserves passage/table structure and passed an actual
rules-only smoke in the sister CLP Python 3.13 environment.

The reconciled universe is 200 sections: 143 positive, 50 true negative, and
seven parser-extension sections excluded from strict acceptance scoring. Of
4,035 source pairs, 3,696 map uniquely and all 339 exclusions are accounted for:
297 repeated short forms, four absent short forms, 33 repeated long forms, and
five absent long forms. A legacy reversed section required 19 explicit semantic
orientation repairs in the derivative snapshot.

Saved rules-only and full decisions were replayed without new model requests.
The full replay scores 0.9888 CLP-native F1 and 0.9886 Abrex exact-offset F1;
the views and denominators remain separate. Existing S&H, Ab3P, PLOD-pairing,
and Jev results, exact error categories, article groups, occurrence examples,
and gold-assisted PLOD ceilings are in
[`artifacts/clp-milestone-a-readout.md`](artifacts/clp-milestone-a-readout.md)
and `evidence/campaign-2026-10/milestone-a/`.

## Verified Milestone B negative result

The authorized Azure OpenAI GPT-6 Luna development run was executed on October
6, 2026. The unchanged frozen prompt first exhausted its 2,048-token output
allowance before emitting structured text. A bounded operational repair retained
the prompt, model, corpus, and scoring policy, raised the allowance to 4,096,
collected failures instead of treating them as empty predictions, disabled
retries, and lowered the remaining-run cap to $0.045 so cumulative spend stayed
below the authorized $0.05.

Eleven of 20 documents returned structured output; nine (45%) again exhausted
all output tokens on reasoning. The 11 scorable documents yielded 14 grounded
predictions: 13 TP, one FP, and 13 FN (precision 0.9286, recall 0.5000, F1
0.6500). These are successful-subset metrics, not a full-run score. The
availability-adjusted descriptive view is precision 0.9286, recall 0.1940, F1
0.3210, while preserving failures as failures. Fifteen of 29 returned pair
proposals (51.7%) were rejected because their literal short-form quotes did not
match the model-supplied offsets. Only one of the 14 relations omitted by the
candidate generators was recovered.

The predeclared reliability, literal-grounding, and candidate-omission-recovery
gates failed. The unchanged direct-extraction prompt therefore does not advance
to Milestone C and must not be rerun merely to obtain a favorable result. Total
provider spend is bounded between $0.0327660 and $0.0471974. The sole exact FP
was a later non-defining occurrence of an already reviewed relation, so there
is no unresolved human adjudication queue.

Authoritative artifacts are
[`artifacts/campaign-2026-10-milestone-b-result.md`](artifacts/campaign-2026-10-milestone-b-result.md),
`evidence/campaign-2026-10/milestone-b/direct-extraction-readout-v1.json`, the
immutable prediction JSONL, and the 11-row successful-response cache. Rebuild
the readout with `scripts/build_direct_extraction_readout.py`. The adapter now
accounts returned token usage even when a response has no structured output.

## Verified Luna quote-grounded refinement

The user authorized up to ten further GPT-6 Luna development iterations with a
separate $0.10 cap for each. The resolver was revised so Luna performs only the
semantic task and copies exact short-form, long-form, and defining-evidence
quotes. Abrex locates those quotes in the unchanged passage and derives Unicode
half-open offsets deterministically. No fuzzy, normalized, candidate-assisted,
or gold-assisted repair is permitted. Low reasoning and an 8,192-token output
allowance replaced the failed medium-reasoning offset-generation contract.

Iteration 1 completed all 20 requests for $0.0048709 and showed that remaining
errors were concentrated in long-form boundary policy and coordinated/elliptical
definitions. The single failure-directed prompt revision in iteration 2 also
completed 20/20 and produced 58 TP, six FP, and nine FN: precision 0.9063,
recall 0.8657, and F1 0.8855. It recovered nine of the 14 relations omitted by
candidate generation. Two of 66 proposals failed exact quote grounding, both
diagnostic representation-limited relations outside strict target scoring.
Actual iteration-2 cost was $0.0055919; cumulative refinement cost was
$0.0104628.

Iteration 2 passed every predeclared development gate and is frozen as
`abrex-quote-grounded-2026-10-06-i02` for new prediction-blind evaluation.
Only two of the ten authorized iterations were used. Further T062 tuning stopped
to avoid overfitting exposed development gold. The consolidated result is
[`artifacts/campaign-2026-10-luna-iteration-result.md`](artifacts/campaign-2026-10-luna-iteration-result.md)
with machine evidence under
`evidence/campaign-2026-10/milestone-b/luna-iterations/`.

## Milestone C frozen sample and review handoff

The scientific lead approved the prepared protocol without revision on October
6, 2026. The immutable approval is
`evidence/campaign-2026-10/milestone-c/protocol-v1.json`. Its preflight records
all six method identities, 238 excluded PMIDs, 83 excluded PMCIDs, known CLP
overlap, the direct-extraction negative result, and the unknown dictionary or
training-overlap limitation. T062 and T067 remain exposed development evidence.

The single frozen source-only draw examined 348 PMC identifiers and selected 72
disjoint article groups after 276 documented exclusions and zero fetch failures.
It contains 48 representative groups with one PMC prose and one linked PubMed
abstract passage each, plus 24 source-structural challenge groups: exactly 120
passages. The source cache preserves 431 URL-addressed responses and 26,643,571
bytes. The representative population is the eligible exact-CC-BY linked
PMC/PubMed frame, not all PubMed. The challenge remains separate and retains
ordered passages, structure, exact raw-source hashes, and serialized source XML.

The frozen six methods are Ab3P, Schwartz–Hearst, PLODv2 pairing, complete CLP
V5.1, Jev candidate judging, and quote-grounded Luna. The two primary contrasts
and Holm-controlled superiority rule are unchanged. The actual blind packet is
`evidence/campaign-2026-10/milestone-c/review-packet-blind-v1.json`, with primary
annotation in progress in its adjacent draft state. New relations default to
abbreviation expansion, contiguous/shared evidence, and text-alone context.
Microsoft Edge QA covered all 120 entries, first/middle/last navigation, the
documented keyboard shortcuts, strict payload isolation, disposable save/reload,
JSON export/import, and incomplete-lock rejection without changing the live
annotation state. The tested human handoff is
[`artifacts/campaign-2026-10-milestone-c-review-guide.md`](artifacts/campaign-2026-10-milestone-c-review-guide.md).

The CLP rules-only dry run applies to the one source-declared ABBR section and
completed as unresolved with zero pairs. The other 23 structural cases are
recorded as not applicable to CLP's ABBR-section contract. The no-call execution
plan contains 64 Jev candidate-judge batches over 42 candidate-bearing passages
plus one CLP Jev request: 65 TypeSafe requests, no retries, no more than 724,000
input tokens and $0.05. The frozen Luna route is 120 requests, no retries, no
more than 201,000 estimated input tokens, 8,192 output tokens per request and
$0.10. No TypeSafe, Luna, or other confirmatory prediction request has been sent;
both remain separately gated until the prediction-blind annotation lock.

The active Windows host still has no installed Ubuntu distribution. This is a
host-prerequisite result, not an Ab3P or PLODv2 failure; post-lock execution must
use the documented fresh Linux server bundle and `setup-runtime.sh` flow.

The repository-wide fast gate passes at this handoff: source-import verification,
Ruff formatting and lint, strict mypy over 214 source files, and 466 passed tests
with one external-runtime test skipped.

## Evidence to retain

- [`T062-development-readout.md`](artifacts/T062-development-readout.md) is the
  reconciled assisted development comparator.
- [`T067-fresh-evaluation-readout-v1.json`](artifacts/T067-fresh-evaluation-readout-v1.json)
  is exposed development evidence, not a repeatedly sampled confirmatory test.
- [`T068-human-next-direction.md`](tasks/T068-human-next-direction.md) preserves
  the prior scientific decision; this campaign supersedes its former
  analysis/design-only scope.
- Historical checkpoints remain under `docs/archive/` for provenance only.
