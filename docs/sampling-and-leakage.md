# Contemporary sampling and leakage controls

T029 provides a deterministic proposal mechanism for contemporary literature
frames. It is an engineering control, not a scientific approval of final
sample sizes or train/dev/test assignments.

## Frame contract

The input is JSONL. Each row has a required `record_id`, optional PMID/PMCID,
source kind (`abstract`, `full_text` or `unknown`), optional source hash/year,
availability, official split and ascertainable teacher-overlap status. Optional
`challenge_tags` identify difficult structures such as tables, captions,
ambiguity or rare forms. Optional `occurrence_keys` are article-level links
already observed in the supplied literature text; they are not inferred from
aggregate frequency counts.

PMID, PMCID and normalized-content identities are grouped before selection.
Near-duplicate grouping uses configurable token-set Jaccard similarity. A
group cannot cross roles. Official historical splits are retained as
`official:<split>` assignments; conflicting declarations are rejected.

## Proposal roles

Roles are configured in YAML. `random` roles use a seeded stable SHA-256 rank;
`challenge` roles select only tagged groups and are reported separately. The
`lexicon_allowed` flag is explicit and is forced false for official and
excluded groups. `derive_lexicon_view` exposes only occurrence links from
allowed records, so evaluation/challenge evidence cannot be used for lexicon
induction, threshold tuning or iteration through this interface.

Sampling probabilities are recorded only for random assignments. They are
frame-level proposal quantities, not population estimates; challenge selections
must remain separate from weighted reporting. Unknown teacher overlap is
retained and counted. Unavailable texts are retained in accounting but never
assigned to a usable role.

The optional T028 SQLite resource contributes aggregate short-form priorities
after sampled article occurrence links exist. It does not supply document
locations, labels or an independent benchmark population.

## Reproduction

The bounded checked-in proposal uses:

```powershell
abrex literature sample --config configs/literature/T029-sampling-proposal.yaml `
  --output .artifacts/T029/sampling-proposal.json
```

The checked-in configuration is intentionally a proposal for target years
2020--2024 and a small abstract/full-text pilot. T047 separately selects the
large-scale discovery/training population. T030 must establish any contemporary
gold annotation and adjudication protocol before scientific evaluation claims.
