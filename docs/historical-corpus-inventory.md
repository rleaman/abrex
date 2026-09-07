# Historical corpus inventory (T019)

This inventory records the source-to-canonical contracts used by the current
historical configurations. Counts and fingerprints below come from the real
local-source audit in [`historical-corpus-audit.json`](artifacts/historical-corpus-audit.json);
raw and canonical data are intentionally not tracked.

| Variant | Annotation unit / coordinate contract | Relation and eligible metric | Official split / source status | Raw records | Raw annotation units | Relation nodes | Canonical records | Canonical annotations | Dropped records | Eligible scoreable units | Source SHA-256 (prefix) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `ab3p_corpus` | paired BioC definitions; Unicode Python half-open | explicit BioC relations, named order fallback; `exact_pair` | corpus-defined; user-managed local | 1,250 | 2,446 | 1,223 | 1,237 | 1,174 | 13 | 0 | `1ebbd44b…e69219` |
| `bioadi` | paired BioC definitions; Unicode Python half-open | explicit BioC relations, named order fallback; `exact_pair` | corpus-defined; user-managed local | 1,201 | 3,440 | 1,720 | 1,185 | 1,670 | 16 | 0 | `2adb6f1b…5d8be5` |
| `medstract` | paired BioC definitions; Unicode Python half-open | explicit BioC relations, named order fallback; `exact_pair` | corpus-defined; user-managed local | 198 | 318 | 159 | 197 | 156 | 1 | 0 | `f9309a81…840ab1` |
| `schwartz_hearst` | paired BioC definitions; Unicode Python half-open | explicit BioC relations, named order fallback; `exact_pair` | corpus-defined; user-managed local | 1,000 | 1,958 | 979 | 991 | 944 | 9 | 0 | `f7ef9fe6…0d3a6` |
| `sdu_aaai21_ai_train` | paired token BIO labels; reconstructed half-open | token labels; `exact_pair` | official train; user-managed local | 14,006 | 37,501 | 0 | 14,006 | 14,006 | 0 | 10,575 | `2a481821…8bbcd` |
| `sdu_aaai21_ad_train` | acronym span plus expansion text; no LF document span | no local pair metric; `not_scoreable` | official train; user-managed local | 50,034 | 50,034 | 0 | 50,034 | 50,034 | 0 | 0 | `bcc5c855…51266a` |
| `sdu_aaai22_ae_english_scientific_train` | independent SF/LF spans; Unicode Python half-open | no pairing; `exact_span` | official English scientific train; user-managed local | 3,980 | 13,404 | 0 | 3,980 | 13,404 | 0 | 13,404 | `00b8fba7…143cdf` |

The BioC source exports contain discontinuous locations that the current
single-span domain model cannot represent as one contiguous `TextSpan`. The
configured `first_location` policy retains the first location and emits a
diagnostic containing the complete source location list; source-text
disagreements are preserved and counted rather than overlaid. The audit found
23, 14, 1 and 10 such annotations in Ab3P, BIOADI, MEDSTRACT and Schwartz &
Hearst respectively. The full diagnostic counts are in the JSON artifact and
the ignored processed manifests.

The `Eligible scoreable units` column applies the declared metric, not the
generic pair-completeness warning. Consequently independent AE spans count as
scoreable for `exact_span`, while every AD row has zero scoreable local pair
units. The pair validator also reports partial AI, AD and AE annotations as
`unscoreable`; those warnings are retained for audit and must not be read as a
license to turn an ineligible benchmark into a pair score.

The corrected `schwartz_hearst_badrex` and `medstract_badrex` variants are
excluded under the [settled availability decision](badrex-availability.md).
They are not missing work items for this inventory.
