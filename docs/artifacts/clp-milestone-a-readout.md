# CLP Milestone A readout

This is risk-stratified development evidence, not independent validation.

## Reconciled source universe

- 200 sections: 143 positive, 50 negative, and 7 parser-extension sections excluded from strict acceptance scoring.
- 4,035 source pairs: 3,696 uniquely mapped to Abrex half-open offsets and 339 explicit mapping exclusions (8.40%).
- The derivative now records 19 semantic-orientation repairs from one legacy reversed section; source strings and provenance remain preserved.

## CLP-native view

| Variant | Mode | Matched / gold | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| Rules-only | cache-only, misses unresolved | 3958 / 4035 | 0.9935 | 0.9809 | 0.9872 |
| Full V5.1 | saved Jev-decision replay | 3971 / 4035 | 0.9935 | 0.9841 | 0.9888 |

## Abrex exact-offset view

| Variant | Precision | Recall | F1 |
|---|---:|---:|---:|
| Rules-only | 0.9923 | 0.9818 | 0.9871 |
| Full V5.1 | 0.9924 | 0.9848 | 0.9886 |

These denominators differ from CLP-native normalized occurrence metrics and are not pooled. Predictions corresponding to the 339 unmapped reference pairs are excluded rather than labeled false positives.

## Full-replay error accounting

{"acceptance": 19, "candidate_omission": 35, "orientation": 2, "source_structure_mapping": 336}

The machine report retains occurrence examples, article identities, pattern strata, source hashes, existing S&H/Ab3P/PLOD/Jev development comparators, and the explicitly gold-assisted PLOD endpoint/pairing ceilings.
