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

The campaign configuration uses the Azure OpenAI v1 Responses API with the
deployment supplied in `AZURE_OPENAI_DEPLOYMENT`, medium reasoning, 2,048
maximum output tokens per document, no automatic retries, at most 20 network
attempts, 25,000 estimated input tokens, and a $0.05 configured run cap. The
previous OpenAI `gpt-6-luna` cost estimate is historical; the Azure deployment
and its billing rates now determine whether the full 20-document run fits this
cap. The exact model identity returned by each response is retained.

## Run

Set these five environment variables in the same PowerShell session as the run:

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

Before running, confirm that this deployment and region support the v1 Responses
API, strict Structured Outputs (`text.format` with JSON Schema), developer
messages, and `reasoning.effort=medium`. The account also needs working API-key
access and network access to the Azure endpoint. Azure's [Responses guide](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
and [structured-output guide](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)
describe these capabilities. The v1 path uses implicit versioning, so no
`AZURE_OPENAI_API_VERSION` variable is needed. If the supplied URL is an older
deployment-scoped API endpoint, obtain the resource base URL for v1.

The $0.05 limit uses the configured per-token rates and returned token counts;
it is an application estimate, not an Azure billing control. Check Azure's
applicable [pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
for your deployment type, region, and contract. A deployment with higher prices
may hit the cap before all 20 documents finish; change the cap only with the
appropriate budget authorization. Access to the API also needs authorization
to send these 20 biomedical passages to this Azure resource.

Once those conditions are met, run:

```powershell
.\env313\Scripts\abrex.exe experiment run configs\experiments\campaign-2026-10-direct-extraction.yaml
```

The input is the reconciled 20-document, 67-relation T062 development artifact.
The run produces immutable predictions, exact-pair evaluation, an error table,
an HTML error report, and a manifest under
`.artifacts/campaign-2026-10/direct-extraction`.
The command's final JSON prints `estimated_total_cost_usd`. The same value is
saved at `resolver.usage.actual_cost_usd` in `run-manifest.json`, alongside the
total input/output tokens and network-attempt count. It is calculated from
returned usage and the configured Azure token rates. A cache-only replay incurs
no new model requests and reports zero for that replay; Azure billing remains
the authority for the final charge.

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
