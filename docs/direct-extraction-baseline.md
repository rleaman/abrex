# Source-grounded direct extraction baseline

The `openai_direct_extraction` resolver asks a structured-output model to find
literal abbreviation relations without first supplying generated candidates.
It therefore measures the direct-extraction alternative to candidate judging,
not another candidate-ranking policy.

## Scientific contract

- Input is the unchanged canonical document text.
- Every short and long form must include an exact quotation and a zero-based,
  Unicode-code-point, half-open occurrence span `[start, end)`.
- The adapter validates `text[start:end] == quote`. It never searches for a
  replacement occurrence, normalizes a quotation, or repairs output from gold.
- Invalid grounded output, duplicate output, explicit abstention, and
  discontinuous evidence receive separate serialized diagnostics.
- Only unique, contiguous, source-validated pairs enter exact-pair scoring.
  Discontinuous evidence stays visible but is not coerced into one exact span.

The stable policy is `source-grounded-direct-v1`; the prompt identity is
`abrex-direct-extraction-2026-10-05-v1`. Both are part of the content-addressed
request identity. The complete JSON Schema is also included in that identity.

## Reproducibility and limits

The configured resolver records the provider response ID, returned model name,
request hash, cache status, latency, token usage, retry attempts, and aggregate
run usage. Cache entries are keyed by the complete request, including text,
prompt, schema, model, reasoning effort, output limit, and provider endpoint;
changing the data destination cannot reuse an old direct-response cache entry.
Every successful document also receives a serialized request-completion
diagnostic containing its response ID, returned model, request hash, latency,
attempt count, and input/output tokens. This remains present for abstentions and
fully rejected output, while aggregate usage separately distinguishes billable
network attempts from direct-cache hits.

The campaign configuration uses the Responses API, `gpt-6-luna`, medium
reasoning, 2,048 maximum output tokens per document, no automatic retries, at
most 20 network attempts, 25,000 estimated input tokens, and a hard $0.05 run
cap. The
[API model page](https://developers.openai.com/api/docs/models/gpt-6-luna)
exposes `gpt-6-luna` as the supported model ID rather than a dated snapshot; the
exact model identity returned by each response is retained.

## Run

After explicitly authorizing the data destination and budget and providing
`OPENAI_API_KEY`, run:

```powershell
.\env313\Scripts\abrex.exe experiment run configs\experiments\campaign-2026-10-direct-extraction.yaml
```

The input is the reconciled 20-document, 67-relation T062 development artifact.
The run produces immutable predictions, exact-pair evaluation, an error table,
an HTML error report, and a manifest under
`.artifacts/campaign-2026-10/direct-extraction`.

Before any external request, the exact campaign configuration is exercised by
an end-to-end local HTTP simulation over all 20 documents. That test traverses
the registry, layered YAML configuration, HTTP request/response boundary,
strict response parsing, direct cache, evaluation, all three reporters, and
aggregate usage in the run manifest. It then removes the test API key, rejects
any attempted network call, and confirms cache-only replay yields the identical
prediction fingerprint. Simulated outputs are confined to pytest temporary
storage and are not scientific evidence.

This development run is assisted evidence for method selection. It is not a
blind validation result and must not be presented as one.
