# Milestone C pre-freeze protocol inventory

Status: prepared for protocol approval; no sample has been drawn and no
Milestone C predictions have been requested. The original Luna prompt is
incorporated as a negative development result, and the separately versioned
quote-grounded revision is incorporated as a gate-passing development result.

## Why T067 cannot be reused

T067 was prediction-blind when annotated, but its results are now exposed and
have been used for method design. It contained only eight article groups and
32 passages, of which 25 were strict negatives. Method gains and errors were
strongly concentrated by article group, so it remains development evidence.

The confirmatory comparison therefore uses a new, single frozen draw and
excludes all linked development, CLP, T065, and T067 identities. The machine
inventory contains 238 excluded PMIDs and 83 excluded PMCIDs with source hashes.
Known CLP article overlap is excluded. Unobservable dictionary or training-data
overlap remains an explicit limitation rather than an assumed negative.

## Proposed sample and burden

The primary representative component uses 48 new article groups, one seeded
PMC prose passage and one linked PubMed abstract passage per group: 96 passages.
No detector, candidate, abbreviation-token heuristic, or prediction is used for
selection. With 48 independent groups, the worst-case Wilson 95% half-width for
a group-level proportion is approximately 0.136. Pair metrics use a seeded
article-group bootstrap rather than treating passages as independent.

A separate structural challenge uses 24 disjoint new article groups and one
source-defined ABBR or table/list section per group. Ordered source passages and
raw table XML are retained so complete CLP V5.1 is evaluated on its structural
contract. This enriched evidence is reported separately and is never pooled
into a population estimate.

The total proposal is 72 article groups and 120 passages, estimated at 8–12
hours of primary annotation. A second reviewer checks all positive, uncertain,
diagnostic, or representation-limited relations plus a seeded 10% of negative
passages before adjudication.

The source-only reviewer has passed a disposable Microsoft Edge/Playwright test
covering payload isolation, Unicode and repeated-text span entry, relation
entry, a zero-relation passage, durable save/reload, JSON export/import,
server-enforced locking, locked export, and a narrow mobile viewport. Evidence
is `evidence/campaign-2026-10/milestone-c/blind-reviewer-qa-v1.json`. The actual
frozen packet will receive the same browser and persistence test before delivery.

## Proposed methods and endpoint

Six methods enter the confirmatory comparison:

- native-offset Ab3P;
- Schwartz–Hearst;
- PLODv2 pairing;
- complete CLP V5.1, with its native normalized view kept separate;
- Jev candidate judging at the existing split-policy thresholds.
- quote-grounded Luna direct extraction, frozen at
  `abrex-quote-grounded-2026-10-06-i02`.

The original offset-producing prompt remains visible as negative development
evidence: nine of 20 requests failed, 15 of 29 proposals failed offset
grounding, and only one of 14 candidate omissions was recovered. The separately
versioned quote-grounded extractor passed every development gate on iteration 2:
20/20 requests completed, exact F1 was 0.8855, nine of 14 omissions were
recovered, and two of 66 proposals failed deterministic grounding. It now
advances in frozen form; the failed prompt does not.

Strict half-open occurrence-pair F1 on the representative component is primary.
The two primary contrasts are complete CLP V5.1 versus Schwartz–Hearst and
quote-grounded Luna versus Jev candidate judging. A superiority statement
requires an absolute F1 gain of at least 0.05 and a paired, seeded
article-group-bootstrap result passing Holm control across both contrasts at
familywise alpha 0.05. Request failures must remain at or below 5%, every
dropped or repaired output must be diagnosed, and all frozen request, token,
and cost limits must hold. The structural challenge remains descriptive and
cannot satisfy a representative superiority criterion. A missed threshold is
reported as “not established”; it does not trigger redrawing, retuning, or
endpoint substitution.

Strict half-open occurrence-pair scoring remains primary for every method.
Endpoint diagnostics, discontinuous evidence, CLP-native string scoring,
abstentions, failures, latency, and actual request usage remain separate.
Results are stratified as representative PMC prose, representative PubMed
abstracts, and structural challenge. Every frozen method is reported even when
negative.

## Decision needed before freeze

The recommended decision is to approve the six-method, 72-group/120-passage
protocol and the two primary contrasts above. Approval authorizes source-only
sampling and acquisition plus construction and testing of the prediction-blind
review packet. It does **not** authorize TypeSafe requests, resolver prediction
runs, annotation reveal, or new Azure requests. TypeSafe receives a separate
bounded request and budget authorization after the actual sample and rules-only
dry run make the request count and cost concrete.

The prefilled decision record is
[`campaign-2026-10-protocol-decision.md`](campaign-2026-10-protocol-decision.md).
The full machine record is
`evidence/campaign-2026-10/milestone-c/preflight-v1.json` and is rebuilt with:

```powershell
.\env313\Scripts\python.exe scripts\build_milestone_c_preflight.py
```

The strict runtime smoke was attempted on the active host. `wsl.exe` returned
installation help because the historical Ubuntu distribution and its
`/home/rleaman` runtime are absent. This is a host-prerequisite failure, not an
Ab3P or PLODv2 failure. Execution therefore follows the documented fresh Linux
server bundle and `setup-runtime.sh` flow. Evidence is retained in
`evidence/campaign-2026-10/milestone-c/runtime-preflight-v1.json`.
