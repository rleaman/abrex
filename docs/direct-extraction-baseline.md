# Source-grounded direct extraction baseline

The `openai_direct_extraction` resolver asks a structured-output model to find
literal abbreviation relations without first supplying generated candidates.
It therefore measures the direct-extraction alternative to candidate judging,
not another candidate-ranking policy.

Status: the original offset-producing Azure development run completed on
October 6, 2026 and failed its predeclared advancement gate. Do not rerun it to
seek a favorable result. A separately versioned quote-grounded refinement then
passed every development gate on its second iteration and is frozen for new
prediction-blind evaluation. See
[`artifacts/campaign-2026-10-milestone-b-result.md`](artifacts/campaign-2026-10-milestone-b-result.md)
and
[`artifacts/campaign-2026-10-luna-iteration-result.md`](artifacts/campaign-2026-10-luna-iteration-result.md).

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

The selected refinement is `abrex-quote-grounded-2026-10-06-i02`. Luna returns
only exact short-form, long-form, and defining-evidence quotations. The resolver
requires unique literal evidence, locates each form inside it, and derives the
canonical offsets mechanically. Missing, repeated, reconstructed, or ambiguous
evidence is diagnosed and dropped. Its append-only attempt ledger records starts
and terminal usage so an interrupted iteration cannot silently repeat a charged
request.

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

The campaign used the Azure OpenAI v1 Responses API with the deployment supplied
in `AZURE_OPENAI_DEPLOYMENT`, medium reasoning, no automatic retries, and at
most one final-batch request per document. The initial 2,048-token allowance was
exhausted on reasoning before output text. The recorded operational repair used
4,096 output tokens and a reduced $0.045 remaining-run cap; it did not change
the prompt, model, corpus, or scoring policy. Returned token usage from failed
structured responses is now charged to the resolver cap. The exact model
identity returned by successful responses is retained.

## Execution record — do not rerun

These five environment variables defined the executed route:

| Variable | Value |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Azure resource URL, such as `https://RESOURCE.openai.azure.com/`, or its `/openai/v1/` base URL. A complete `/openai/v1/responses` URL also works. Do not include a deployment path, `api-version`, or key in the URL. |
| `AZURE_OPENAI_API_KEY` | API key for that resource. Keep it out of YAML, logs, and version control. |
| `AZURE_OPENAI_DEPLOYMENT` | The **deployment name** (which may differ from the underlying model name). |
| `AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS` | Your Azure input-token price in USD per million tokens for this deployment and billing arrangement. |
| `AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS` | The matching output-token price in USD per million tokens. |

For example, set them from your Azure resource and pricing information (the
values below are placeholders, not prices):

```powershell
$env:AZURE_OPENAI_ENDPOINT = 'https://RESOURCE.openai.azure.com/'
$env:AZURE_OPENAI_API_KEY = '<your-key>'
$env:AZURE_OPENAI_DEPLOYMENT = '<deployment-name>'
$env:AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS = '<input-price>'
$env:AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS = '<output-price>'
```

The key is read only when a live response is requested. The other four values
are required to resolve this campaign YAML. The resolved deployment, endpoint,
and price assumptions are recorded in the run manifest; the key is not.

The deployment and region supported the v1 Responses API, strict Structured
Outputs (`text.format` with JSON Schema), developer messages, and
`reasoning.effort=medium`. Azure's [Responses guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
and [structured-output guide](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)
describe these capabilities. The v1 path uses implicit versioning, so no
`AZURE_OPENAI_API_VERSION` variable is needed. If the supplied URL is an older
deployment-scoped API endpoint, obtain the resource base URL for v1.

The $0.05 authorization used the supplied per-token rates and returned token
counts; it was an application bound, not an Azure billing control. Total spend
is bounded between $0.0327660 and $0.0471974.

The executed command was:

```powershell
.\env313\Scripts\abrex.exe experiment run configs\experiments\campaign-2026-10-direct-extraction.yaml
```

The evaluator correctly refused to score nine runtime failures as empty
predictions, so the generic runner did not publish a misleading final manifest.
The failure-aware campaign readout instead binds the immutable prediction JSONL,
the 11 successful cached responses, exact successful-subset metrics, the
availability-adjusted descriptive view, and the cost bound. No further Azure
request is needed for this development comparison.

Before live execution, the exact campaign configuration was exercised by an
end-to-end local HTTP simulation over all 20 documents. That test traversed
the registry, layered YAML configuration, HTTP request/response boundary,
strict response parsing, direct cache, evaluation, all three reporters, and
aggregate usage in the run manifest. It then removed the test API key, rejected
any attempted network call, and confirmed cache-only replay yielded the identical
prediction fingerprint. Simulated outputs are confined to pytest temporary
storage and are not scientific evidence.

This development run is assisted evidence for method selection. It is not a
blind validation result and must not be presented as one.
