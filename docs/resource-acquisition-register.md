# External abbreviation resource acquisition register

Updated September 7, 2026. This register separates candidate resources from files actually acquired. The new [complete resource catalog](resource-catalog.md) preserves all 41 records from the supplied CSV, including citations, unnamed entries, tools and corpora. [T046](tasks/T046-external-dictionary-acquisition.md) owns acquisition and source audits; [T028](tasks/T028-lexical-resource-ingestion.md) owns storage/query interfaces; [T034](tasks/T034-lexical-candidates-and-evidence-features.md) owns scientific use.

| Resource | Why it is on the list | Current acquisition status | Next action |
| --- | --- | --- | --- |
| 2024 abbreviation frequency JSON | User-supplied literature-derived evidence | Present at data/raw/resources/abbr_frequency_2024.json.gz (Git-ignored); structurally inspected, aggregate counts without article links | T028 streaming ingestion and provenance clarification |
| ADAM | Explicit user suggestion; external MEDLINE abbreviation resource | Not acquired; supplied landing page returned 502 through the planning browser | T046 investigate official bulk endpoint or supplied copy; preserve source version and variant grouping |
| ALLIE | Original idea and CSV row 6 | Official landing and download directory opened; files not acquired | T046 select/version an official extract and verify fields and terms |
| Acromine | CSV rows 7 and 16 | Official REST documentation opened; actual access/query behavior unverified | T046 verify access and preserve counts/variants; no assumed bulk export |
| SaRAD, Stanford Biomedical Abbreviation Server, ARGH, AcroMed | CSV dictionary references | Discovery candidates; current download endpoints unknown | T046 investigate official sources while available-source work proceeds |
| Terminology exports, including UMLS if available | Named in the original idea; may add different term/abbreviation evidence | No local export supplied | Inventory permitted user exports and source concept/sense IDs; do not assume access |
| Further user suggestions | CSV now incorporated | All 41 rows cataloged; additional suggestions can be appended | Retain original citations and distinguish duplicate references from distinct resources |

The [ADAM publication](https://pubmed.ncbi.nlm.nih.gov/16982707/) describes an abbreviation database from MEDLINE and a bulk text download. That historical description does not verify a current download endpoint. The [user-supplied landing page](http://abel.lis.illinois.edu/adam.html) could not be retrieved in this session; retain the failure as an access observation, not a conclusion that the resource is permanently unavailable.

Each acquired source needs its own manifest: source URL or local origin, release/retrieval date, byte hash, extraction method/source family, license/access evidence, format, grouping/normalization semantics, count unit, article/context availability and record reconciliation. Report overlap and correlated extraction provenance before combining sources as evidence. Raw inputs remain immutable.

## Software and corpus routing

[T048](tasks/T048-bioadi-runtime-and-resolver.md) explicitly assesses BioADI software: the supplied JAR returned HTTP 200 and a 5,237,679-byte Java archive Content-Type/length in a header check. It was not downloaded or executed. The BioADI corpus remains in T019. NatLAb, AbbrAlignHMM, ALICE, BLAR and other named tools remain documented follow-up candidates, not silently omitted or automatically committed integrations.

T019 handles existing corpus references; new corpora such as ALICE require explicit source semantics and follow-up scope. Dictionary discovery routes to T046; paper-only and nonlocal-disambiguation references stay in the catalog for review. The catalog records the primary links supporting current access observations.
