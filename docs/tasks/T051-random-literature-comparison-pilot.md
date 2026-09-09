# T051 Acquire and compare the bounded random-literature pilot

Status: Authorized after T050. Implementer: GPT-5.6 Luna.

## Outcome and dependencies

Produce actual source and prediction artifacts for the [current-work protocol](../CURRENT_WORK.md): 10 CC BY PMC full texts and 20 PubMed titles/abstracts. Dependencies are working source checks and existing acquisition, BioC/JATS, article mapping and resolver APIs; inspect their implementation and runtime instructions as needed, not all historical tasks.

## Implementation

1. Add typed YAML/CLI orchestration around existing application services. Use current official NCBI acquisition APIs and their rate limits. Verify current endpoint behavior; do not assume the older FTP distribution still works. No network-dependent unit tests.
2. Implement reproducible random selection and per-article license verification exactly as current work specifies. Record seed/frame identity or numeric bounds, every attempted identifier, eligibility, exclusion/failure reason, timestamp, raw response hash, source version and counterpart grouping. Respect the local budget and preserve replay without redownload.
3. Download immutable Unicode BioC XML and source JATS for the PMC arm, plus title/abstract XML and BioC representation for the PubMed arm. Preserve raw formats outside Git; source provenance, source text and explicit coordinate mapping must survive normalization. Confirm that an article's license applies to the article rather than a quoted/reference license. Do not conflate CC BY with restricted variants.
4. Run all three primary resolvers and the existing hybrid on identical canonical sections/documents under a recorded segmentation policy. Include title text. Preserve PLOD independent spans and full-text window coverage. Store method/config/runtime/model identity, prediction hashes, exact offsets, failures, runtime and output volume. Do not treat a model failure as empty output or replace a selected article because it is difficult.
5. Run separately labeled existing structural/lexical candidate paths where inputs exist; retain method failures/unavailable inputs separately. No need to complete training, pattern induction, BioADI or acquire a new bulk dictionary.
6. Derive agreement/disagreement inventories from occurrence-level spans and explicit policies, distinguishing relation, boundary and unpaired-span differences. Build machine-readable passage inventories for T052, including successful all-method-zero passages and abbreviation heuristic features. No accuracy metrics without reviewed labels.
7. Compare BioC and JATS text/structures in at least three selected full texts. Keep table rows/cells, abbreviation/definition lists, captions and footnotes distinct. Report loss, reordering, unsupported structures and mapping failures; do not force one format's offsets into the other. If the random sample lacks a structure, report that gap; do not quietly enrich the document sample.

## Acceptance and verification

- Target 10 verified CC BY full texts and 20 unique noncounterpart abstract records, with reconciled attempts/exclusions/selected/processed/failed counts. If an external service prevents the target within budget, report partial status and continue independent interface work; do not declare the real-run criterion complete.
- Every canonical prediction slices back to the recorded text, and source mapping is reconstructable or explicitly unresolved.
- Real executions and artifact-derived comparisons exist; offline fixtures alone do not satisfy this task.
- Tests cover deterministic selection/replay, license variant rejection, identifier grouping, limits, retries/failures, Unicode offsets and text/structure comparison. Run canonical fast/full gates and diff checks.

## Deliverables

Reproducible YAML/commands, ignored raw/prediction artifacts, small tracked manifest/summary with counts/hashes/runtime/limitations and a readable source comparison. Update index and write `completed/T051-random-literature-comparison-pilot.md` only for satisfied acceptance scope. Continue to T052; do not wait for human annotation.

## Primary references

- https://pmc.ncbi.nlm.nih.gov/tools/articles-by-license/
- https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/
- https://pmc.ncbi.nlm.nih.gov/tools/textmining/
