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

## Milestone B status and exact dependency

Local Milestone B preparation is complete. A registry-backed
`openai_direct_extraction` resolver can propose pairs absent from generated
candidates, uses strict Structured Outputs, validates literal Unicode half-open
offsets, keeps discontinuous evidence separate, serializes abstention/rejection
diagnostics, uses content-addressed caching, and enforces request/token/retry and
monetary limits. Aggregate actual usage is included in experiment manifests.

The current T062 development ledger has been materialized as an immutable
20-document, 67-relation canonical dataset at
`evidence/campaign-2026-10/milestone-b/`. Five overlap warnings are preserved;
no relation is dropped. The prior recommended OpenAI pilot was `gpt-6-luna`,
medium reasoning, 20 requests, at most 2,048 output tokens each, no automatic
retries, and a $0.05 configured cap. Its $0.0222 conservative maximum-token
estimate applies only to that prior OpenAI price route. The current campaign
YAML instead targets the user's Azure OpenAI deployment and requires its actual
input/output token rates.
The current candidate generators produce 742 proposals, cover 53/67 strict
relations (79.1%), and omit 14 before judging; the occurrence-level report is
`evidence/campaign-2026-10/milestone-b/direct-extraction-preflight-v1.json`.
See
[`artifacts/campaign-2026-10-milestone-b-preflight.md`](artifacts/campaign-2026-10-milestone-b-preflight.md)
and [`direct-extraction-baseline.md`](direct-extraction-baseline.md).
The Azure campaign YAML has passed a disposable 20-document end-to-end local
HTTP simulation, including manifest usage and a no-key/no-network direct-cache
replay with the same prediction fingerprint. These synthetic outputs were kept
out of campaign evidence and are not scientific results.
The direct-response cache key also binds the provider and endpoint, so changing the
scientific-data destination cannot silently reuse an old response.
Resolver version 2 serializes per-document request completion metadata even for
abstentions and fully rejected output: response/model identity, request hash,
latency, attempt count, and token usage. Aggregate run usage also distinguishes
billable network attempts from direct-cache hits.
The campaign command now prints `estimated_total_cost_usd` in its final JSON,
using the same aggregate returned-token cost saved in
`run-manifest.json` at `resolver.usage.actual_cost_usd`.
The repository fast gate passes after this CLI change: format, lint, strict
mypy, 454 tests passed, and one external-runtime test was skipped.

No external request has been issued. The campaign YAML now selects the Azure
OpenAI v1 Responses API and accepts a resource endpoint plus deployment name.
Set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
`AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS`, and
`AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS` as described in
[`direct-extraction-baseline.md`](direct-extraction-baseline.md). Confirm the
deployment supports strict Structured Outputs and medium reasoning, and confirm
authorization to send the 20 biomedical passages to this Azure resource under
the configured $0.05 cap. Once ready, run:

```powershell
.\env313\Scripts\abrex.exe experiment run configs\experiments\campaign-2026-10-direct-extraction.yaml
```

The owner must then validate actual usage and failure/abstention rates, compare
candidate coverage and exact errors on all 67 relations, prepare only genuinely
unresolved assisted review, and continue into the Milestone C protocol without
another implementation assignment.

## Milestone C independent pre-freeze preparation

The exposed T067 sample is now treated as development evidence and will not be
reused for confirmation. A machine-checked preflight at
`evidence/campaign-2026-10/milestone-c/preflight-v1.json` inventories all six
requested method identities, 238 excluded PMIDs, 83 excluded PMCIDs, known CLP
overlap, and the unknown dictionary/training-overlap limitation. See
[`artifacts/campaign-2026-10-milestone-c-preflight.md`](artifacts/campaign-2026-10-milestone-c-preflight.md).

The unfrozen workload proposal is 48 representative groups with one PMC prose
and one linked PubMed abstract passage each, plus 24 disjoint source-structural
challenge groups: 72 groups and 120 passages total, estimated at 8–12 primary
review hours. The representative group count gives an approximate worst-case
Wilson 95% half-width of 0.136 for a group-level proportion. The challenge is
reported separately and retains the ordered passages and raw table XML needed
by complete CLP V5.1. Final freeze awaits Milestone B results, bounded external
request authorization, and approval of review burden and success thresholds;
no Milestone C sampling or predictions have been issued.

The same machine preflight now carries explicit unfrozen success criteria rather
than leaving them for post-result invention. The recommended Milestone B gate
requires recovery of at least seven of the 14 candidate-omitted relations,
exact precision of at least 0.65, at most 5% request failure, at most 10% invalid
grounded output, and the $0.05 cap in one unchanged-prompt run. Confirmatory
superiority requires an absolute representative exact-F1 gain of at least 0.05
plus a paired group-bootstrap result passing Holm control across the two primary
contrasts. Structural-challenge evidence cannot satisfy that claim. These values
are proposals awaiting the eventual protocol decision, not frozen policy.

The prediction-blind reviewer has also passed a fresh campaign-specific,
disposable Microsoft Edge/Playwright exercise covering payload isolation,
Unicode/repeated-text span entry, zero-relation completion, save/reload, JSON
backup/import, server-enforced lock/export, and a 390-by-844 viewport. Evidence
is in
`evidence/campaign-2026-10/milestone-c/blind-reviewer-qa-v1.json`. The actual
frozen packet will be browser-tested again before delivery; no human annotation
has been fabricated by this QA.

The baseline runtime guide's strict WSL smoke was attempted and failed before
resolver execution because the active host has no installed Ubuntu distribution;
`wsl.exe` returned installation help. This is not a method failure, and the user
cannot install WSL here. The frozen comparison must use the documented fresh
Linux server bundle and `setup-runtime.sh` flow. Exact evidence is in
`evidence/campaign-2026-10/milestone-c/runtime-preflight-v1.json`.

## Evidence to retain

- [`T062-development-readout.md`](artifacts/T062-development-readout.md) is the
  reconciled assisted development comparator.
- [`T067-fresh-evaluation-readout-v1.json`](artifacts/T067-fresh-evaluation-readout-v1.json)
  is exposed development evidence, not a repeatedly sampled confirmatory test.
- [`T068-human-next-direction.md`](tasks/T068-human-next-direction.md) preserves
  the prior scientific decision; this campaign supersedes its former
  analysis/design-only scope.
- Historical checkpoints remain under `docs/archive/` for provenance only.
