# Current work: random-literature plumbing and review pilot

Decision date: September 8, 2026. Recovery implementers: GPT-5.6 Sol / High,
orchestrated in the current task; independent acceptance review: GPT-6 Astra / High.

## Authorized outcome

The user approved proceeding with a small random PMC/PubMed pilot, real method comparisons, JATS/BioC inspection and a usable human review interface. Execute [T050](tasks/T050-source-verification-repair.md) → [T051](tasks/T051-random-literature-comparison-pilot.md) → [T052](tasks/T052-pilot-annotation-interface.md). Continue through these tasks without asking the user to approve routine engineering. Deliver the actual review packet and working interface, not just a plan or XML file. Human annotation happens afterward and is not a blocker to delivering the pilot.

## Decisions made for this pilot

- Target 10 randomly selected PMC full texts with verified **CC BY** article licenses. CC0 is outside this particular pilot following the user's latest wording; CC BY-NC/ND/SA are not CC BY. Preserve exact license version, URL/text and evidence source for every accepted article. Unknown/conflicting license evidence means exclusion, not assumed eligibility.
- Separately sample 20 PubMed records with nonempty abstracts; include title and abstract as separately identifiable sections. PubMed availability does not confer CC BY. Retain provenance and use these in local review; do not label or package them as CC BY full texts.
- No topic, date or model-output enrichment of document selection. Freeze the sampling date, observed frame or identifier bounds, seed `20260908`, draws and exclusions. Random identifier rejection sampling is acceptable if bounds are verified and every draw has equal probability; a documented identifier-frame sample is equally acceptable. Do not call the first search results random.
- Keep linked PMID/PMCID articles in one article group; avoid overlap between the two arms by recording and replacing abstract-arm counterparts. All selected articles are exploratory development material, never an untouched final holdout.
- Save Unicode BioC XML and source JATS for all 10 PMC articles where retrievable. Preserve both versions and compare representations without pretending their offsets coincide. At least three articles receive detailed text/structure audits; include tables/abbreviation lists when the random sample contains them. Do not replace articles merely to obtain particular structures.
- Compare native-offset Ab3P, Schwartz–Hearst and pinned PLODv2 pairing on identical canonical text, plus the transparent hybrid. Retain independent PLOD spans. Structural and lexical candidates are separately labeled proposals. BioADI and iterative training are not prerequisites.
- First review batch: at most 60 cases, initially 30 disagreements, 10 agreements, 15 no-definition-detected passages enriched for abbreviation-like tokens, and 5 uniformly selected no-definition-detected passages. Select deterministically, limit any article to four cases, balance the two source arms where available, and report shortages/selection denominators. These are review-budget settings, not scientific prevalence weights.
- A no-definition-detected passage requires successful coverage by all three primary methods and zero accepted definition pairs intersecting it; unpaired PLOD spans are allowed and useful. Failed/truncated/unprocessed passages are separate diagnostics, never negatives.
- Use a named configurable abbreviation-likelihood heuristic (capitalized/mixed-case/alphanumeric forms and bounded context). It selects review candidates only, never labels truth. Keep enriched and uniform controls separate: abbreviations are not always conspicuous, and scientific names/units may resemble abbreviations.
- Preserve exact pair/span semantics. Review outcomes are assisted expert judgments when suggestions are visible, even if method names are hidden; no fabricated independent gold or precision/recall over unreviewed text.

## Review interface choice

Use a small local browser reviewer as the guaranteed deliverable, with BioC XML import/export for TeamTat portability. Reuse existing reporting/annotation infrastructure; do not build accounts, collaboration or a hosted service. Include readable source context, highlighted alternatives, source/JATS comparison for selected structural cases, accept/reject/uncertain, span correction/addition and missing-definition entry, notes, save/resume and downloadable annotations. Keep method identities hidden initially with an explicit reveal control. TeamTat is an optional alternative, not an account/login dependency for this pilot.

TeamTat documents BioC upload, preannotation and entity/relation annotation at https://www.teamtat.org/. XML validity alone does not prove TeamTat interoperability: verify a small import/export if accessible; otherwise accurately label compatibility unverified while shipping the tested local reviewer. No publication, account creation, invitation, paid service or unattended work-scale processing is part of this milestone.

## Scope and stopping

Use bounded local processing. Set explicit acquisition attempts/bytes/retry/time limits and resolver limits in the implementation; proposed defaults are at most 1,000 identifier draws per arm, 200 MiB total source downloads and four hours total pilot execution. Record reached limits, allow deterministic resume, and do not silently replace processing failures with successful articles. Metadata discovery is separately counted/bounded; avoid downloading an entire large corpus to select 30 articles. Adjust operational settings with a documented reason if necessary, without broadening the 30-article target or launching bulk processing.

Fix source/release verification now. T036 pattern promotion, T038 training integration, T039 research-loop execution and a full T040 learning campaign remain recorded follow-up work; they must not delay this pilot, which does not use them. Derive the new pilot report from actual manifests/predictions instead of copying T040's hard-coded report mechanism. Preserve [the September 8 audit](project-status-review-2026-09-08.md) as history.

## Reading and status discipline

Recovery status: the user authorized Sol/High subagents for verification,
scientific-pipeline repair, and reviewer repair, followed by independent
Astra/High acceptance review. See the [implementation audit](reviewer-implementation-audit-2026-09-08.md).
The existing v1 30-record run and 60-case packet remain preserved development
artifacts, not accepted protocol-compliant comparison output. The repaired v2
run is now at `.artifacts/T051/random-pilot-v2/` with a content-hashed manifest
and the corrected packet is at `.artifacts/T052/review-packet-v2.json` with a
new content-derived identity. It contains 60 explicitly labeled
method-availability diagnostics because Ab3P and PLODv2 were unavailable on the
bounded host; strict agreement/disagreement/no-definition strata remain
shortages, never negatives. T050 is engineering-verified; T051/T052 remain
partial pending optional-method prerequisites and actual browser QA.

T050 verification tooling and source-import regression coverage are in place.
The September 9 source checkpoint passes import-origin verification, Ruff,
strict mypy, the 350-test fast gate and isolated wheel smoke. The full coverage
gate currently reports 87.77% across 356 tests because the new pilot/reviewer
orchestration branches need a separate coverage-focused pass; no threshold was
lowered or exclusion added. The v2 run records 10 CC BY PMC articles, 20
PubMed abstract records, 74 attempts, 44 exclusions and 1,567 inventories.

The repaired interface must clearly identify the article and source type,
label and visually bound the **Passage to review**, preserve paragraph breaks,
and distinguish annotatable passage text from optional surrounding context.
Use separate prompts for checking a proposed definition and finding missed
definitions. Highlight abbreviation/expansion spans with labels, support text
selection for corrections, and put parser paths, offsets and raw structure
details outside the main review flow. Human annotations remain human work.

Read AGENTS.md, this file, the current assigned task and relevant interfaces/contracts. Historical task specifications and completed notes stay where they are to preserve links and provenance; they need not be reread wholesale. Update the task index with separate engineering, real-run and review-delivery status. Do not relabel the entire project complete. The BADREX exclusion is settled.

The milestone is delivered when the bounded source/prediction artifacts and useful first review batch actually exist, the reviewer passes save/edit/reload/import checks, and the source quality gate passes. User review and all later research claims remain pending explicitly.
