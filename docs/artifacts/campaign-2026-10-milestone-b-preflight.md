# Milestone B direct-extraction preflight

No scientific-data API request has been sent.

## Ready inputs and comparator

- Reconciled input: 20 documents, 25,020 canonical text characters, 67 strict
  exact relations, and five retained overlap warnings.
- Candidate-judge comparator on the same reconciled development ledger: 25 TP,
  11 FP, two outside-target predictions, 42 FN; precision 0.694, recall 0.373,
  F1 0.485.
- Current configured candidate generators produce 742 proposals and cover
  53/67 strict relations (79.1%); 14/67 are candidate omissions before judging.
  The machine report retains all 14 exact occurrences.
- Historical generator coverage diagnostic on the earlier 59-relation view:
  47/59 relations had a generated candidate and 12/59 were candidate omissions.
  This is not silently substituted for coverage on the reconciled 67 relations.

## Recommended bounded route

Run all 20 development documents once with `gpt-6-luna`, medium reasoning, and
strict Structured Outputs. This is the smallest complete comparison on the
same development inputs; a smaller subset would not answer the campaign's
candidate-coverage question.

The serialized requests contain 68,640 characters. The conservative local
estimate is 17,152 input tokens. With 40,960 aggregate maximum output tokens,
the configured standard-price upper estimate is $0.0222. The runtime hard cap
is $0.05, covering estimation error while preventing unbounded use. Automatic
retries are disabled, so at most one billable request is attempted per document.
The current published standard prices used here are $0.10/M input tokens and
[$0.50/M output tokens](https://developers.openai.com/api/docs/models/gpt-6-luna).

## Completed validation

- The YAML resolves and constructs through the normal resolver registry.
- Unicode literal grounding, unsupported-output diagnostics, discontinuous
  evidence separation, deduplication, abstention, retries, cache-only replay,
  request/token/cost limits, and registry construction have focused tests.
- Run manifests retain aggregate resolver usage and cache-hit counts. Every
  document prediction record, including abstentions and fully rejected output,
  has a request-completion diagnostic with response ID, model, request hash,
  latency, attempts, and token usage.
- The reconciled development materializer validates all 67 literal pairs and
  records the five known overlap warnings without dropping any relation.

Remaining dependency: explicit authorization to send these 20 biomedical text
passages to the OpenAI Responses API under a $0.05 maximum, plus an API key in
`OPENAI_API_KEY`. Once available, the owner runs, imports, analyzes, and prepares
any genuinely unresolved review queue without a new implementation assignment.

The exact campaign YAML has also passed a 20-document end-to-end local HTTP
simulation through the registry, structured Responses adapter, grounding and
diagnostics, direct cache, evaluator, reporters, and usage manifest. A second
run removed the test key, prohibited network access, and reproduced the same
prediction fingerprint from the direct cache. All simulated responses and run
artifacts were disposable and are not model results.

The cache identity also binds the provider endpoint. A destination change now
forces a cache miss, preventing responses obtained from one endpoint from being
silently reused for another.
