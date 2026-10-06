# Milestone C pre-freeze protocol inventory

This is a prepared proposal, not a frozen protocol. Milestone B's direct
extraction result must be incorporated before the method and success-criteria
freeze.

## Why T067 cannot be reused

T067 was prediction-blind when annotated, but its results are now exposed and
have been used for method design. It contained only eight article groups and
32 passages, of which 25 were strict negatives. Method gains and errors were
strongly concentrated by article group. It remains development evidence.

The next comparison therefore uses a new, single frozen draw and excludes all
linked development, CLP, T065, and T067 identities. The machine inventory
currently contains 238 excluded PMIDs and 83 excluded PMCIDs with source hashes.
Known CLP article overlap is excluded. Unobservable dictionary or training-data
overlap remains an explicit limitation rather than an assumed negative.

## Proposed sample and burden

The primary representative component uses 48 new article groups, one seeded
PMC prose passage and one linked PubMed abstract passage per group: 96 passages.
No detector, candidate, abbreviation-token heuristic, or prediction is used for
selection. With 48 independent groups, the worst-case Wilson 95% half-width for
a group-level proportion is approximately 0.136; pair metrics will use a seeded
article-group bootstrap rather than pretending passages are independent.

A separate structural challenge uses 24 disjoint new article groups and one
source-defined ABBR or table/list section per group. Ordered source passages and
raw table XML must be retained so the complete CLP parser is evaluated on its
actual structural contract. Its enriched results are reported separately and
never pooled into a population estimate.

Total proposed primary work is 72 article groups and 120 passages. Estimated
primary annotation burden is 8–12 hours. A second reviewer checks all positive,
uncertain, diagnostic, or representation-limited relations plus a seeded 10%
of negative passages before adjudication. The existing blind reviewer supplies
navigation, whole-passage search, save/resume, span entry, and immutable lock;
the actual acquired packet must pass browser and disposable persistence tests
before delivery.

The source-only interface itself has now passed a fresh disposable Microsoft
Edge/Playwright run for this campaign. The run verified that the browser/API
payload contains no assisted-output fields, then exercised Unicode and repeated
text selection, relation entry, a zero-relation passage, durable save/reload,
JSON export/import, server-enforced locking, locked export, and a narrow mobile
viewport. Its machine evidence is
`evidence/campaign-2026-10/milestone-c/blind-reviewer-qa-v1.json`. This proves
interface readiness only; the eventual frozen packet still receives the same
QA before human delivery.

## Proposed success criteria

These thresholds are a pre-result recommendation, not yet frozen. The unchanged
Milestone B prompt advances only if its single 20-document run recovers at least
seven of the 14 gold relations omitted by the candidate generators, achieves at
least 0.65 exact precision, has at most one failed request (5%), keeps invalid
grounded output at or below 10% of returned proposals, and stays within the
$0.05 cap. The run is not repeated or tuned merely to cross this gate. A failure
is retained as a negative development result.

For the representative confirmatory component, strict exact-pair F1 is primary.
The two proposed primary contrasts are direct extraction versus Jev candidate
judging and complete CLP V5.1 versus Schwartz–Hearst. A superiority statement
requires both an absolute F1 gain of at least 0.05 and a paired, seeded
article-group-bootstrap result passing Holm control across the two contrasts at
familywise alpha 0.05. Request failures must remain at or below 5%, every dropped
or repaired output must be diagnosed, and all frozen request/token/cost limits
must hold. The structural challenge remains descriptive and cannot satisfy the
representative superiority criterion. Results that miss a threshold are
reported as “not established”; they do not trigger redrawing or endpoint
substitution.

The rationale is deliberately conservative: the development gate requires the
direct method to recover at least half of the known candidate ceiling loss while
retaining usable precision, and the confirmatory rule requires both statistical
and practical evidence. Final thresholds remain an explicit human scientific
decision after the Milestone B result is available.

## Frozen comparison contents

The comparison keeps every requested method visible:

- native-offset Ab3P;
- Schwartz–Hearst;
- PLODv2 pairing;
- complete CLP V5.1, with its native normalized view kept separate;
- Jev candidate judging at the existing split-policy thresholds;
- source-grounded direct extraction, if the unchanged development prompt is
  advanced after Milestone B.

Strict half-open occurrence-pair scoring is primary. Endpoint diagnostics,
discontinuous evidence, CLP-native string scoring, abstentions, failures,
latency, and actual request usage remain separate. Results are stratified as
representative PMC prose, representative PubMed abstracts, and structural
challenge. Every frozen method is reported even when negative, and the sample
is never redrawn to obtain a favorable result.

## Remaining pre-freeze decisions

The local identities, exclusions, workload, and runtime boundaries are ready.
Freezing still requires the Milestone B direct-extraction result, explicit
Azure OpenAI and TypeSafe scientific-data request authorization, and approval of the
final workload and success thresholds. No sampling or prediction request has
been issued for Milestone C.

The full machine record is
`evidence/campaign-2026-10/milestone-c/preflight-v1.json` and is rebuilt with:

```powershell
.\env313\Scripts\python.exe scripts\build_milestone_c_preflight.py
```

The required strict runtime smoke was attempted on the active host. `wsl.exe`
returned installation help because the historical Ubuntu distribution and its
`/home/rleaman` runtime are not present. This is a verified host-prerequisite
failure, not an Ab3P or PLODv2 failure. The confirmatory run therefore follows
the already recorded fresh Linux server provisioning decision and bundle setup
flow. Exact evidence is retained in
`evidence/campaign-2026-10/milestone-c/runtime-preflight-v1.json`.
