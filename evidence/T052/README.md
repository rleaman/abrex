# T052 review-pilot evidence bundle

Status: frozen final review evidence  
Freeze date: September 10, 2026

This directory preserves the data presented during the T052 browser review,
the complete final annotation state, the source selection and method-output
evidence needed to interpret the packet, and a final BioC interchange export.
It is the evidence bundle for the scientific-model iteration
[Interpretive grounding from the T052 pilot](../../docs/scientific-model/2026-09-10-interpretive-grounding.md).

The files in this directory are immutable historical evidence. Do not edit or
replace them in place. Corrections or later adjudication must create a new
versioned evidence bundle that cites this one and explains the change.

## Contents

- [`manifest.json`](manifest.json) records provenance, the explicit public
  distribution policy, file roles, byte sizes and SHA-256 hashes.
- [`T051-pilot-manifest.json`](T051-pilot-manifest.json) preserves the sampled
  records, canonical sections, selection inventories, method outputs,
  diagnostics, source URLs and license evidence from the v2 pilot run.
- [`review-packet-v2.json`](review-packet-v2.json) is the immutable 60-case
  packet shown to the reviewer, including bounded passages, suggestions,
  context, selection reasons and method diagnostics.
- [`review-packet-v2.annotations.final.json`](review-packet-v2.annotations.final.json)
  is the completed review state. It contains all 60 case annotations and the
  full ordered revision history.
- [`review-packet-v2.final.bioc.xml`](review-packet-v2.final.bioc.xml) is a new
  BioC export generated from the final annotation state and validated by
  importing it back to an identical state.
- [`review-packet-build-summary.json`](review-packet-build-summary.json) is the
  earlier tracked construction summary. It describes the packet before human
  review and must not be mistaken for the final outcome summary.
- [`outcome-summary.json`](outcome-summary.json) contains the final descriptive
  disposition counts and interpretation limits.

## Scientific interpretation limits

The review is assisted, provisional scientific evidence rather than an
independently annotated gold benchmark. The packet was diagnostically selected,
and all 79 visible machine suggestions came from Schwartz-Hearst because Ab3P
and PLODv2 were unavailable for the bounded run. The disposition counts must
not be reported as precision, recall or population prevalence.

The final state contains 105 pair decisions: 103 correct, two incorrect, and no
remaining unsure or unreviewed judgments. Twenty-six pairs were added by the
reviewer across ten cases. These observations motivated the provisional
interpretive-grounding hierarchy, taxonomy and dimensions recorded in the
linked scientific-model iteration.

## Public distribution policy

The user made an explicit scientific-policy decision on September 10, 2026,
authorizing preservation and possible public sharing of this complete bundle.
The ten PMC records have source-verified CC BY licenses in the source manifest.
The PubMed arm contains only titles and abstracts from a bounded 20-record
scientific sample; the project treats sharing this non-substantial sample as
fair use.

This is a decision for this evidence bundle. It does not automatically authorize
future packets, larger PubMed collections, different PMC license families or
third-party material not covered by an article's recorded license.

## Integrity and validation

`manifest.json` records the SHA-256 hash and byte size of every evidence file
other than this explanatory README and the manifest itself. The packet also has
an internal content identity: its `packet_content_sha256` is calculated from the
identity payload and therefore differs from the hash of the complete JSON file
that contains that identity.

The final annotation JSON was validated against the immutable packet using the
repository's typed review contracts. The final BioC XML was generated with
`write_bioc_xml` and read back with `import_bioc_xml`; the restored state equaled
the frozen annotation state, including revision history embedded in the BioC
sidecar metadata.

The bundle records the source Git commit and that the workspace contained
uncommitted documentation/evidence changes when it was frozen. Scientific
identity is therefore anchored primarily by the preserved inputs and their
hashes rather than by a claim that the source worktree was clean.

