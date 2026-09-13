# Scientific model iteration: development challenge freeze

Status: iteration 0.2; operational development subset frozen September 13, 2026
Evidence date: September 12, 2026

This iteration follows, but does not rewrite, the
[September 10 interpretive-grounding model](2026-09-10-interpretive-grounding.md).
It uses the user's returned T056 assisted review state, the 20-passage T053
challenge selection, and the separately recorded policy statement that
abbreviations and labels form a continuum and that figure visuals are out of
scope for now.

## What changed

The returned state contains 60 searched cases and 111 current relations: 110
supported and one unsupported; 32 additions, five corrected suggestions and
74 unchanged assisted suggestions. Compared with the September 10 frozen
state, this is six more current relations. Across all 60 cases, 67 relations
are called abbreviation expansions, seven other naming/code relations and 37
uncertain. The completed 20-passage challenge subset contains 72 relations:
59 strict exact pairs, 13 explicit diagnostic relations and none unresolved.

The review sharpened three distinctions:

- A supported relation can be outside strict abbreviation extraction. `7n`,
  `G'`, `G"`, `HBO2`, `tcPO2`, `tcPCO2`, and `all-cause death` were explicitly
  classified as other naming or code relations.
- A supported abbreviation relation can be unrepresentable as one exact pair.
  The experimental-group forms and several shared lipid mappings were marked
  discontinuous and retain their evidence fragments.
- Lexical meaning and manuscript evidence can disagree. The `CT` note records
  the Taxol/paclitaxel mismatch without replacing the literal manuscript span.

## Positive, negative, and uncertain examples

Positive strict candidates include `ATX` → `adjuvant therapy`, `T2HR` →
`high-resolution T2-weighted imaging`, and the contiguous lipid mappings that
the user explicitly classified as abbreviation expansions. Eligibility for a
metric also depends on completion of the whole passage policy audit.

Positive broader grounding examples include `7n` → `facial motor nucleus` and
`G'` → `elastic modulus`. They are supported relations worth preserving for
error analysis, but the user's explicit neighboring-relation label keeps them
outside the strict task. The `tcPCO2` example adds `Transcutaneous` as a
separate evidence fragment, demonstrating why a continuous bounding span
would misrepresent coordination ellipsis.

The rejected `arrow` suggestion remains a negative textual-pair example.
Visual arrows, colors and other figure content are out of scope for this
iteration even though they remain examples in the broader interpretive-
grounding model.

Uncertain examples remain among non-challenge T052 pairs whose new
relation-kind field was left `uncertain`, along with the precise general
boundary among `O2`, `G'`, `7n` and `ATX`, the manuscript/source treatment of
`CT`, and any automatic splitting of lists or ratios. These are not negative
examples and are not clean passage denominators.

## Model consequence

The broad-evidence-layer plus named-projection architecture remains useful, but
the T057 evidence supports only one narrow projection:
`t057-strict-exact-pair-v1`. It requires explicit support, explicit
abbreviation classification, contiguous shared evidence, text-only context,
literal source spans and no source-error flag. Diagnostic evidence preserves
neighboring, discontinuous, unsupported and source-error relations. Unresolved
relations remain in the complete 60-case ledger but not in the frozen challenge
subset.

This iteration rejects the idea that a broad positive filter can define the
evaluation universe. Later predictions must be compared with the frozen scope
policy: explicit neighboring relations are classified as outside target;
unresolved or incompletely searched passages are unscoreable; and unmatched
predictions on complete in-scope passages remain false positives.

## Still unresolved

- No universal boundary separates abbreviation, label, symbol and derived
  short name.
- T057 does not decide whether source-brand equivalence licenses a manuscript
  expansion that was not literally written.
- It does not define a general decomposition rule for lists, ratios,
  coordination ellipsis or one-to-many mappings.
- It does not create a relaxed metric or certify any diagnostic relation as an
  exact pair.
- The returned legacy state records assisted exposure but not a reviewer ID;
  provenance therefore relies on the T056 completion record and file hash.
- The development material remains diagnostically selected and cannot support
  an independent-gold or untouched-test claim.
