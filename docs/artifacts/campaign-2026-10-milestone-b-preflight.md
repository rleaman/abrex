# Milestone B direct-extraction preflight (historical)

Status: executed on October 6, 2026. This file preserves the pre-run design;
it is not a run instruction. The authoritative outcome is
[`campaign-2026-10-milestone-b-result.md`](campaign-2026-10-milestone-b-result.md).
The Azure authorization and credentials dependency was satisfied. Do not rerun
the unchanged prompt merely to seek a favorable result.

## Inputs and comparator fixed before execution

- Reconciled input: 20 documents, 25,020 canonical text characters, 67 strict
  exact relations, and five retained overlap warnings.
- Candidate-judge comparator on the same reconciled development ledger: 25 TP,
  11 FP, two outside-target predictions, and 42 FN; precision 0.694, recall
  0.373, F1 0.485.
- The configured candidate generators produced 742 proposals and covered 53/67
  strict relations (79.1%); 14/67 were candidate omissions before judging. The
  machine report retained all 14 exact occurrences.
- The historical generator diagnostic on the earlier 59-relation view was
  47/59 covered and 12/59 omitted. It was not substituted for the reconciled
  67-relation denominator.

## Bounded route that was authorized

All 20 development documents were assigned once to the supplied Azure OpenAI
deployment, which resolved exactly to `gpt-6-luna`, with medium reasoning and
strict Structured Outputs. The serialized requests contained 68,640
characters and had a conservative local input estimate of 17,152 tokens.
Automatic retries were disabled and the aggregate hard cap was $0.05.

The original 2,048-token output allowance produced no structured text on the
first document. A bounded operational repair kept the prompt, model, corpus,
and scoring policy unchanged, raised the allowance to 4,096, collected failed
responses rather than scoring them as empty predictions, and lowered the
remaining-run cap to $0.045. The complete provider spend is bounded between
$0.0327660 and $0.0471974, below authorization.

## Validation completed before execution

- The YAML resolved and constructed through the normal resolver registry.
- Unicode literal grounding, unsupported-output diagnostics, discontinuous
  evidence separation, deduplication, abstention, retries, cache-only replay,
  request/token/cost limits, and registry construction had focused tests.
- Run manifests retained aggregate resolver usage and cache-hit counts. Every
  successful document record had a request-completion diagnostic with response
  ID, model, request hash, latency, attempts, and token usage.
- The reconciled development materializer validated all 67 literal pairs and
  recorded the five known overlap warnings without dropping a relation.
- A 20-document local HTTP simulation exercised the registry, Azure-compatible
  Responses adapter, grounding, diagnostics, direct cache, evaluator, reporters,
  and usage manifest. Cache-only replay reproduced the prediction fingerprint
  with network prohibited.
- Cache identity bound the provider endpoint, preventing responses obtained
  from one destination from being silently reused for another.

## Recorded outcome

Eleven documents returned structured output and nine exhausted 4,096 output
tokens on reasoning. The predeclared request-reliability, literal-grounding,
and candidate-omission-recovery gates failed. The direct extractor is retained
as negative development evidence and is excluded from new Milestone C requests.
No unresolved human adjudication remains. See the result readout for exact
metrics, hashes, costs, and the advancement decision.
