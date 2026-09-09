# T050–T052 implementation and reviewer audit

Reviewed September 8, 2026 (local date), against current task specifications, source, saved pilot artifacts, and the existing Chrome reviewer. No production code or user annotation files were changed.

## Verdict

The milestone is incomplete. T050 has an import-isolation change but fails acceptance. T051 has real acquisition artifacts and Schwartz–Hearst output, but does not implement the approved random selection or method comparison. T052 has a functioning page and JSON persistence, but its packet is incorrectly aligned and required annotation/interchange behavior is absent. Notes in `docs/tasks/completed/` themselves describe T051 and T052 as partial deliveries.

## Findings, in repair order

1. **P1: Suggestions lose their passage identity.** `pilot.py` combines section-relative predictions into an article-wide array without section IDs. `review.py:91` attaches that array's first three suggestions to every section. In the actual packet, 132 of 144 suggestion occurrences fail exact SF/LF text slicing against the displayed passage. Case 2 discusses UE/HSHFD but suggests Igf2/Jz/Lz, none of which occur in that passage. Structures likewise come from the first eight article structures rather than the displayed passage. Preserve section identity and immutable canonical text, then regenerate the packet without overwriting existing annotations.
2. **P1: Sampling violates the authorized protocol.** `pilot.py:143` requests the first 100 PMC search results, filters to 2020–2024, and shuffles them; PubMed similarly uses the first 60 matching results. This is not the approved unrestricted random sample. The frozen identifier frame, successful draw log, replay/resume mechanism and source comparison are absent. The manifest confirms the date filter. Preserve this run as a development fixture and obtain a protocol-compliant sample separately.
3. **P1: Required comparison methods are never attempted.** `pilot.py:251` hard-codes Ab3P and PLODv2 as unavailable and hybrid as not run. It does not probe their installation or execute configured adapters. The manifest and tracked summary confirm only Schwartz–Hearst ran. Agreement/disagreement and all-method-zero inventories therefore do not exist. The 60 cases are 55 assisted suggestions and five unreviewed controls, with 40 PMC and 20 PubMed cases; they do not fulfill the requested strata.
4. **P1: Saved decisions are absent from BioC downloads.** `/api/bioc` serves the original static XML; POST only writes the separate JSON annotations file. The XML writer never merges those saved decisions. No JSON or BioC import flow exists, and no relation endpoints are exported. A downloadable XML response is not an annotation round trip.
5. **P1: Annotation validation and identity protection are insufficient.** POST accepts arbitrary JSON without validating schema, packet identity, case IDs, spans or text. Packet IDs hash the manifest path and sequential case IDs, so changed content at the same path with the same case count retains the ID. Browser span parsing permits offsets past the passage length and uses UTF-16 `slice`, inconsistent with canonical Unicode character offsets for supplementary characters. Only one SF/LF pair is represented per case, so alternatives/multiple definitions cannot be preserved. Revisions are counters, not preserved edit history.
6. **P1: Source strings are inserted as HTML.** Suggestions and structures are interpolated into `innerHTML` without escaping, contrary to T052's explicit requirement. Render source text with text nodes.
7. **P2: Navigation can discard work.** Clicking a case directly calls `show` without saving or guarding edits. Previous/Next proceed even when save catches a validation or server failure. Saved indication persists across case changes. Filters affect sidebar visibility but not navigation and have no All reset.
8. **P2: Operational limits are incomplete.** `max_bytes` caps each individual response, not the aggregate download; the accumulated counter is not enforced. PubMed attempts are neither counted nor bounded by `max_attempts`. There is no overall elapsed-time limit, checkpoint resume or bounded retry policy. The manifest's 68 attempts covers PMC, while its selected count includes 20 additional PubMed records.
9. **P2: T050 checks remain incomplete.** Required coverage and normal gate do not pass; a separate wheel smoke and T050 completion note are not delivered. The new pilot/reviewer test file contains only three tests and does not exercise acquisition, packet selection, HTTP decisions or browser behavior. Its Unicode example tests Greek alpha, not supplementary characters, and does not validate span text against the passage.

## Verification performed

Used Python 3.13 with `PYTHONPATH=src;env313/Lib/site-packages` as documented in the partial completion notes.

- Focused tests: `py -3.13 -m pytest tests/unit/test_t051_t052_pilot.py tests/unit/test_quality_gate.py tests/unit/test_t022_smoke.py -q`: 6 passed.
- Source suite: `py -3.13 -m pytest --cov --cov-report=term --basetemp .pytest-tmp/reviewer-audit -q`: 315 passed; coverage 92.15%, failing required 95%.
- Canonical fast gate: `py -3.13 scripts/quality_gate.py`: failed at Ruff executable lookup. Strict mypy and remaining gate stages were not reached.
- Read the real manifest and packet: 10 PMC records, 20 PubMed records, 58 exclusions; 60 cases; 132/144 displayed suggestion occurrences fail exact passage slicing.
- Inspected current Chrome page and scrolled to suggestions. Did not save experimental judgments into the user's packet; two saved annotation entries existed at inspection time.

## Observed reviewer flow and simplification

1. **Read case — confusing.** The passage itself is readable, but its heading is a parser path. The 60-row sidebar uses white button text on a white background, leaving identifiers effectively invisible. No plain-language instruction explains the decision. Screenshot: `../.artifacts/reviewer-audit/01-current-case.png`.
2. **Compare suggestions — incorrect context.** Suggestions sit beneath the paragraph rather than highlighted within it and do not belong to the displayed passage. The raw source-structure list is unrelated to the paragraph. Screenshot: `../.artifacts/reviewer-audit/02-suggestions.png`.
3. **Decide/correct — incomplete.** One status dropdown must somehow describe three suggestions. Corrections require manually calculated offsets with no text-selection tool. Keep one decision per proposed pair, plus a distinct passage check for missed definitions. Offer Correct / Incorrect / Unsure, an Edit selection action, and Add a missed definition.
4. **Save/resume/export — unreliable.** Server persistence exists but navigation and export defects above prevent a trustworthy complete workflow. Use explicit Save and next with failure recovery, reviewed/remaining progress, resume at last case, and tested backup import/export. Keep provenance, methods and structured source comparison behind Details, with a clearly labeled source-article link.

Recommended main screen: progress and article title; one sentence explaining the review question; a passage with distinguishable SF/LF highlights and a legend; the proposed abbreviation–expansion pair; clear decision buttons; optional corrections/notes; Save and next. Article IDs, parser paths, seeds, hashes and numeric offsets belong in optional technical details. Controls must handle multiple definitions without flattening their scientific meaning.

Accessibility findings are limited to observed layout, text contrast and control labels plus source inspection. Keyboard, screen-reader, responsive layout and full annotation round-trip tests remain to be executed on the repaired interface. This was a read-only audit, not acceptance of the reviewer.

## Recovery follow-up

The user subsequently authorized orchestrated Sol/High repairs and independent
Astra/High acceptance review. During that work, five regression cases exposed
additional PubMed source issues: title-only and whitespace-only abstract
eligibility, reference-list PMC IDs contaminating source identity, and silently
discarded extra articles in a batch response. `parsers.py` now scopes primary
metadata correctly, requires a nonempty abstract even when including a title,
and rejects multiple articles rather than silently choosing one. The five new
regressions and existing literature tests passed together (27 tests). This is
repair evidence, not retrospective acceptance of the original pilot artifacts.
