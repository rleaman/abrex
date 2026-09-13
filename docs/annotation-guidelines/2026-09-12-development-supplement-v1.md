# Development guideline supplement T057-v1

Status: frozen development policy; accepted September 13, 2026
Evidence date: September 12, 2026
Base guidelines: [T030-v1](../annotation-guidelines.md)

This supplement operationalizes distinctions explicitly recorded by the user in
the returned T056 assisted review. It does not turn unset audit fields into
scientific judgments and does not define a relaxed metric.

## Strict abbreviation inclusion

A relation enters the named `t057-strict-exact-pair-v1` view only when all of
the following are explicit in the returned state:

1. the relation is supported (`correct`);
2. its relation kind is `abbreviation_expansion`;
3. it has exact short- and long-form source spans;
4. its evidence structure is `contiguous_shared`;
5. text alone supplies the required context; and
6. no source error is flagged.

Both spans retain their literal half-open Unicode coordinates. Internal
punctuation or digits that belong to a form remain included. Surrounding
punctuation and parentheses do not. Repeated occurrences remain separate.
`ATX` → `adjuvant therapy`, the explicitly classified lipid forms, and the
explicitly classified `T2HR`/`T2S` relations are positive examples when they
also satisfy the passage-level completeness rule below.

An `arrow` parser proposal is a negative example: it is unsupported and visual
figure content is outside the current strict target. `7n` → `facial motor
nucleus`, `G'` → `elastic modulus`, and `all-cause death` → `death from any
cause` are retained as supported neighboring relations, not strict pairs.

## Evidence fragments and reconstruction

The short- and long-form fields always quote exact contiguous source text.
Additional evidence fragments are ordered, independently exact source spans;
they must never overlap or be duplicated, and they must never be merged by
expanding across intervening text.

When the intended interpretation requires material that is not one contiguous
source span, mark the structure `discontinuous` and retain every available
fragment. Such a relation is diagnostic and not representable by the exact-pair
view. The reviewed `tcPCO2` relation, whose long-form field is `carbon dioxide`
and whose additional fragment is `Transcutaneous`, is the positive example.

A reconstructed interpretation is a plain-text interpretation labeled
`reconstructed`. It has no source coordinates and can never substitute for a
long-form source span in exact scoring. The returned review contains no
nonempty reconstruction, so policy exists but no reconstructed claim is made.

## Source errors

Retain exactly what the source printed. A suspected correction is diagnostic
metadata and never replaces source text or inherits its coordinates. A flagged
source error stays outside the strict view until separately adjudicated. The
anomalous `HDL1-PL` relation is flagged as a source error. Its literal printed
long-form evidence is retained as `2`; T057 does not infer an intended
scientific correction or silently relabel it as `HDL2-PL`.

The `CT` example is also unresolved for strict inclusion: the user noted that
Taxol is the brand name for paclitaxel and that `CT` abbreviates
`cisplatin/Taxol`, while the manuscript presents generic `paclitaxel`. The note
is retained; T057 does not repair the manuscript or infer a strict pair.

## Lists, ratios, and component mappings

Annotate only the mapping actually selected by the reviewer. Do not split a
list or ratio automatically and do not infer component relations from domain
knowledge. The returned whole-span `VLDL3-C, VLDL4-C` mapping and lipid ratios
remain exactly as selected. Any additional component mapping needs its own
source-supported relation and review.

One anchor with alternatives must remain an explicit unresolved alternatives
structure rather than being forced into one pair. The legacy T052 return cannot
encode that structure, so no alternative is inferred during T057.

## Abbreviations, labels, and the continuum

The user found a continuum between lexical abbreviation, derived short name,
scientific symbol, and document-local label. `O2`, `G'`, `7n`, and `ATX` are
boundary examples. T057 respects the user's relation-level choices but does
not promote them into a universal rule:

- explicit `abbreviation_expansion` choices can enter the strict view when all
  other criteria are met;
- explicit `other_naming_or_code_relation` choices stay in the diagnostic
  view; and
- `uncertain` or unset choices remain unresolved and outside scored claims.

`D-group`, `N-group`, `C-group`, and `H-group` were explicitly treated as
abbreviation expansions with discontinuous shared `group` evidence. They are
therefore supported challenge relations but not exact-pair scoreable. This does
not settle whether all experimental-group mnemonics are abbreviations.

## Passage completeness and later predictions

A passage is eligible for ordinary precision/recall denominators only when the
whole passage was marked searched and every retained relation has a resolved
strict/diagnostic disposition. A partially searched passage, an unresolved
support decision, or an unresolved policy field makes the case ineligible. A
failure or unresolved case is never converted into a clean negative.

On an eligible passage, an unmatched in-scope prediction is a false positive.
A prediction matching a relation explicitly marked outside the strict target
is reported as `outside_strict_target`, not silently discarded by a positive
filter. Predictions on incomplete or unresolved passages are retained for
review but cannot form ordinary precision/recall denominators.

## Provenance and limits

The T056 return is assisted development evidence. It is linked by hash to the
September 10 frozen T052 state and to the T053 challenge selection. It is not
independent gold, an untouched test set, a prevalence sample, or evidence for
method superiority. All 20 challenge passages have complete policy fields;
unresolved non-challenge items remain available for later adjudication.
