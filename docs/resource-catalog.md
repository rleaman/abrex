# Catalog of supplied abbreviation resources

Reviewed September 7, 2026. All 41 CSV records are retained, including duplicate references and unnamed entries. Row numbers include the header as row 1. Categories and task routing are planning interpretations; original fields are preserved below. File contents are reference material, not instructions.

[Source CSV](<../handoff/Abbreviation Resolution Resources.csv>)

Source SHA-256: 3cee5f2e10358fb98cfd915c4bdd651cf2cd5b523eb5ec4d3ff6036179efb5e9.

## Acquisition and integration priorities

1. T046 acquires dictionaries: pursue available ALLIE access and Acromine access alongside ADAM investigation. Citation-only dictionaries remain discovery candidates, not promised downloads.
2. T048 assesses the reachable BioADI artifact and integrates a resolver if runtime/provenance checks pass. Its dataset remains in T019.
3. T019 reconciles corpus references with existing adapters. ALICE or other new corpora need source/annotation review before additional integration scope.
4. Other systems remain named follow-up candidates. Availability, output-contract compatibility, source independence and a small complementarity pilot should justify additional assignments. No blanket commitment to implement all papers.

## Verified access observations

- BioADI: a host HTTP HEAD request to the [supplied JAR](https://clojars.org/repo/edu/sinica/bioagent/bioadi/0.1.0/bioadi-0.1.0.jar) returned 200, Content-Length 5237679 and application/x-java-archive. Binary integrity, packaging and execution are untested.
- [ALLIE](https://allie.dbcls.jp/en) links an accessible [official download directory](https://ftp.dbcls.jp/allie/) with large archives and ALICE-output/RDF directories. Listings have differing dates; do not call every file the current service snapshot. No bulk download was performed.
- [Acromine documentation](https://www.nactem.ac.uk/software/acromine/rest.html) describes JSON lookups with counts and variants and includes a Request Access link. Documentation availability does not establish granted access, working queries or bulk export rights.
- ALLIE states that it uses ALICE and retains PubMed identifiers. Preserve this shared lineage and verify downloaded fields before promising article-level occurrence links. ALICE and ALLIE are not independent teachers. [Official description](https://allie.dbcls.jp/en)
- ADAM access was inconclusive earlier (502). Links not explicitly marked checked remain unverified, not dead.

## Complete row inventory

| CSV row | Year | Source resource label | Category | Task route | Access or interpretation |
| --- | --- | --- | --- | --- | --- |
| 2 | 2014 | REVIEW: Schwartz & Hearst, Ab3P & NatLAb | Review | T019 / T048 | Same BioC paper as row 3; retain both source entries. |
| 3 | 2014 | REVIEW: S&H, Medstract, Ab3P & BIOADI | Review | T019 / T048 | Same paper as row 2; not an independent resource. |
| 4 | 2012 | Tool:AbbrAlignHMM | Tool | T048 follow-up candidate | Source URL supplied; browser fetch inconclusive. Build/model requirements unverified. |
| 5 | 2011 | Tool:NatLAb | Tool | T048 follow-up candidate | NatLAb artifact and runtime unverified. |
| 6 | 2011 | ALLIE | Dictionary | T046 / T028 / T034 | ALLIE official landing/download directory opened; bulk files not acquired. |
| 7 | 2010 | AcroMine | Dictionary/API | T046 / T028 / T034 | REST documentation opened; actual access/query behavior unverified. Same family as row 16. |
| 8 | 2009 | MBA | System/reference | T048 follow-up candidate | Paper supplied; implementation availability unknown. |
| 9 | 2009 | Tool:BIOADI | Tool | T048 | JAR HEAD returned 200, 5237679 bytes, application/x-java-archive. Not downloaded or executed. |
| 10 | 2009 | Corpus:BIOADI | Corpus | T019 | Existing BioADI corpus adapter; distinct from the software. |
| 11 | 2009 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 12 | 2008 | Tool:Ab3P | Tool | T018–T022 | Existing Ab3P execution plan. |
| 13 | 2008 | Corpus:Ab3P | Corpus | T019 | Existing Ab3P corpus audit. |
| 14 | 2007 | Tool:AbbrevExtractor | Tool | T048 follow-up candidate | Implementation availability unknown. |
| 15 | 2007 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 16 | 2006 | AcroMine | Dictionary/API | T046 / T028 / T034 | Same Acromine endpoint as row 7; retain both publications. |
| 17 | 2006 | Database:ADAM | Dictionary | T046 / T028 / T034 | ADAM landing fetch returned 502 earlier; bulk availability unresolved. |
| 18 | 2005 | Tool:ALICE | Tool | T048 follow-up candidate | CSV says replaced by ALLIE; distinguish extractor and derived database. Historical URL unverified. |
| 19 | 2005 | Corpus:ALICE | Corpus | T019 follow-up candidate | ALICE corpus URL supplied; source/annotation audit before any new adapter. |
| 20 | 2005 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 21 | 2005 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 22 | 2005 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 23 | 2005 | Unnamed in CSV | Review | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 24 | 2004 | Database:SaRAD | Dictionary | T046 discovery candidate | SaRAD citation only; acquisition endpoint unknown. |
| 25 | 2003 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 26 | 2003 | Tool: ExtractAbbrev / Schwartz & Hearst | Tool | T012 / T022 | Existing Schwartz–Hearst baseline; variants remain explicit. |
| 27 | 2003 | Corpus: Schwartz & Hearst | Corpus | T019 | Existing Schwartz–Hearst corpus audit. |
| 28 | 2002 | Database:Stanford Biomedical Abbreviation Server | Dictionary | T046 discovery candidate | Stanford server citation only; acquisition endpoint unknown. |
| 29 | 2002 | Tool:AbbRE | Tool | T048 follow-up candidate | AbbRE citation only; implementation availability unknown. |
| 30 | 2002 | Corpus:Medstract | Corpus | T019 | MEDSTRACT family; preserve both citations without double counting row 32. |
| 31 | 2002 | Database:ARGH | Dictionary | T046 discovery candidate | ARGH publication supplied; acquisition endpoint unknown. |
| 32 | 2001 | Corpus:Medstract | Corpus | T019 | MEDSTRACT family, also row 30. |
| 33 | 2001 | Database:AcroMed | Dictionary | T046 discovery candidate | AcroMed citation only; acquisition endpoint unknown. |
| 34 | 2000 | Tool:Acrophile | Tool | T048 follow-up candidate | Acrophile availability and domain fit unverified. |
| 35 | 2000 | Unnamed in CSV | Paper-only reference | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 36 | Unspecified | Unnamed in CSV | Review | Research reference | Preserved for scientific review; no downloadable artifact established. |
| 37 | 2022 | Unnamed in CSV | Shared-task reference | T019 | Inspect task/split/label definitions; not automatically paired local-definition gold. |
| 38 | 2021 | Tool: MadDog | Tool | T048 follow-up candidate | MadDog identification/disambiguation; verify local-definition fit and availability. |
| 39 | 2020 | Corpus: Acronym Identification | Corpus | T019 | Reconcile with existing SDU adapters and official versions. |
| 40 | 2019 | Tool: DECBAE | Tool/reference | Separate-scope candidate | DECBAE output/task suitability needs review. |
| 41 | Unspecified | Corpus, Clinical | Corpus/reference | Separate-scope candidate | MeDAL citation supplied; CSV category does not establish source/gold semantics. |
| 42 | 2021 | Tool: BLAR | Tool | T048 follow-up candidate | BLAR implementation/model access unverified. |

## Original citation and link ledger

Source spelling, notes and blank fields are retained. Prose in ALICE URL fields remains a source note; URLs are extracted separately for navigation.

### CSV row 2

Resource: REVIEW: Schwartz & Hearst, Ab3P & NatLAb. Year: 2014. Notes: Review.

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: https://academic.oup.com/database/article/doi/10.1093/database/bau044/2634328

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: [link](https://academic.oup.com/database/article/doi/10.1093/database/bau044/2634328).

Citation: Islamaj Doğan, Rezarta, et al. "Finding abbreviations in biomedical literature: three BioC-compatible modules and four BioC-formatted corpora." Database 2014 (2014).

### CSV row 3

Resource: REVIEW: S&H, Medstract, Ab3P & BIOADI. Year: 2014. Notes: Review.

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: https://academic.oup.com/database/article/doi/10.1093/database/bau044/2634328

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: [link](https://academic.oup.com/database/article/doi/10.1093/database/bau044/2634328).

Citation: Islamaj Doğan, Rezarta, et al. "Finding abbreviations in biomedical literature: three BioC-compatible modules and four BioC-formatted corpora." Database 2014 (2014).

### CSV row 4

Resource: Tool:AbbrAlignHMM. Year: 2012. Notes: (none).

Resource URL field: https://github.com/TeamCohen/secondstring/blob/master/src/com/wcohen/ss/expt/ExtractAbbreviations.java

Paper URL field: http://www.cs.cmu.edu/~dmovshov/papers/dma_abbvAlignment_bioNLP2012.pdf

Resource navigation: [link](https://github.com/TeamCohen/secondstring/blob/master/src/com/wcohen/ss/expt/ExtractAbbreviations.java). Paper: [link](http://www.cs.cmu.edu/~dmovshov/papers/dma_abbvAlignment_bioNLP2012.pdf).

Citation: Movshovitz-Attias, Dana, and William W. Cohen. "Alignment-HMM-based extraction of abbreviations from biomedical text." Proceedings of the 2012 Workshop on Biomedical Natural Language Processing. Association for Computational Linguistics, 2012.

### CSV row 5

Resource: Tool:NatLAb. Year: 2011. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-12-S3-S6

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: [link](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-12-S3-S6).

Citation: Yeganova, Lana, Donald C. Comeau, and W. John Wilbur. "Machine learning with naturally labeled data for identifying abbreviation definitions." BMC bioinformatics 12.3 (2011): S6.

### CSV row 6

Resource: ALLIE. Year: 2011. Notes: (none).

Resource URL field: http://allie.dbcls.jp/

Paper URL field: (not supplied)

Resource navigation: [link](http://allie.dbcls.jp/). Paper: Not supplied.

Citation: Y. Yamamoto, A. Yamaguchi, H. Bono and T. Takagi, "Allie: a database and a search service of abbreviations and long forms.", Database, 2011:bar03.

### CSV row 7

Resource: AcroMine. Year: 2010. Notes: (none).

Resource URL field: http://www.nactem.ac.uk/software/acromine/rest.html

Paper URL field: (not supplied)

Resource navigation: [link](http://www.nactem.ac.uk/software/acromine/rest.html). Paper: Not supplied.

Citation: Okazaki, N., Ananiadou, S., & Tsujii, J. (2010). Building a high quality sense inventory for improved abbreviation disambiguation. Bioinformatics, 26(9), 1246–1253.

### CSV row 8

Resource: MBA. Year: 2009. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-14

Resource navigation: Not supplied. Paper: [link](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-14).

Citation: Xu, Yun, et al. "MBA: a literature mining system for extracting biomedical abbreviations." BMC bioinformatics 10.1 (2009): 14.

### CSV row 9

Resource: Tool:BIOADI. Year: 2009. Notes: (none).

Resource URL field: https://clojars.org/repo/edu/sinica/bioagent/bioadi/0.1.0/bioadi-0.1.0.jar

Paper URL field: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-S15-S7

Resource navigation: [link](https://clojars.org/repo/edu/sinica/bioagent/bioadi/0.1.0/bioadi-0.1.0.jar). Paper: [link](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-S15-S7).

Citation: Kuo C.J. Ling M.H. Lin K.T. et al.  . ( 2009 ) BIOADI: a machine learning approach to identifying abbreviations and definitions in biological literature . BMC Bioinformatics  , 10 , S7 .

### CSV row 10

Resource: Corpus:BIOADI. Year: 2009. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-S15-S7

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: [link](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-S15-S7).

Citation: Kuo C.J. Ling M.H. Lin K.T. et al.  . ( 2009 ) BIOADI: a machine learning approach to identifying abbreviations and definitions in biological literature . BMC Bioinformatics  , 10 , S7 .

### CSV row 11

Resource: (not supplied). Year: 2009. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Sun, X., Okazaki, N., & Tsujii, J. (2009). Robust approach to abbreviating terms—a discriminative latent variable model with global information. In K. Su , J. Su , & J. Wiebe (Eds.), Proceedings of the Joint Conference of the 47th Annual Meeting of the ACL and the 4th International Joint Conference on Natural Language Processing of the AFNLP (ACL‐IJCNLP) (pp. 905–913). Stroudsburg, PA: ACM.

### CSV row 12

Resource: Tool:Ab3P. Year: 2008. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-9-402

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: [link](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-9-402).

Citation: Sohn S. Comeau D.C. Kim W. et al.  . ( 2008 ) Abbreviation definition identification based on automatic precision estimates . BMC Bioinformatics  , 9 , 402 .

### CSV row 13

Resource: Corpus:Ab3P. Year: 2008. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-9-402

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: [link](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-9-402).

Citation: Sohn S. Comeau D.C. Kim W. et al.  . ( 2008 ) Abbreviation definition identification based on automatic precision estimates . BMC Bioinformatics  , 9 , 402 .

### CSV row 14

Resource: Tool:AbbrevExtractor. Year: 2007. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: https://ieeexplore.ieee.org/abstract/document/4413035

Resource navigation: Not supplied. Paper: [link](https://ieeexplore.ieee.org/abstract/document/4413035).

Citation: Song, Min, and Illhoi Yoo. "A Hybrid Abbreviation Extraction Technique for Biomedical Literature." 2007 IEEE International Conference on Bioinformatics and Biomedicine (BIBM 2007). IEEE, 2007.

### CSV row 15

Resource: (not supplied). Year: 2007. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Torii M, Hu ZZ, Song M, Wu CH, Liu H: A comparison study on algorithms of detecting long forms for short forms in biomedical text. BMC Bioinformatics. 2007, 8 (Suppl 9): S5-10.1186/1471-2105-8-S9-S5.

### CSV row 16

Resource: AcroMine. Year: 2006. Notes: (none).

Resource URL field: http://www.nactem.ac.uk/software/acromine/rest.html

Paper URL field: (not supplied)

Resource navigation: [link](http://www.nactem.ac.uk/software/acromine/rest.html). Paper: Not supplied.

Citation: Okazaki, N., & Ananiadou, S. (2006). Building an abbreviation dictionary using a term recognition approach. Bioinformatics, 22(24), 3089–3095.

### CSV row 17

Resource: Database:ADAM. Year: 2006. Notes: (none).

Resource URL field: http://abel.lis.illinois.edu/adam.html

Paper URL field: https://academic.oup.com/bioinformatics/article/22/22/2813/197656

Resource navigation: [link](http://abel.lis.illinois.edu/adam.html). Paper: [link](https://academic.oup.com/bioinformatics/article/22/22/2813/197656).

Citation: Zhou, Wei, Vetle I. Torvik, and Neil R. Smalheiser. "ADAM: another database of abbreviations in MEDLINE." Bioinformatics 22.22 (2006): 2813-2818.

### CSV row 18

Resource: Tool:ALICE. Year: 2005. Notes: (none).

Resource URL field: Replaced by ALLIE, but at http://3.uvdb.dbcls.jp/ALICE/program_download.html

Paper URL field: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1205607/

Resource navigation: [link](http://3.uvdb.dbcls.jp/ALICE/program_download.html). Paper: [link](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1205607/).

Citation: H. Ao, T. Takagi, "ALICE: An algorithm to extract abbreviations from MEDLINE", Journal of the American Medical Informatics Association, vol. 12, pp. 576-586, 2005.

### CSV row 19

Resource: Corpus:ALICE. Year: 2005. Notes: (none).

Resource URL field: Replaced by ALLIE, but at http://3.uvdb.dbcls.jp/ALICE/corpus_download.html

Paper URL field: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1205607/

Resource navigation: [link](http://3.uvdb.dbcls.jp/ALICE/corpus_download.html). Paper: [link](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1205607/).

Citation: H. Ao, T. Takagi, "ALICE: An algorithm to extract abbreviations from MEDLINE", Journal of the American Medical Informatics Association, vol. 12, pp. 576-586, 2005.

### CSV row 20

Resource: (not supplied). Year: 2005. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Bracewell, David B., Scott Russell, and Annie S. Wu. "Identification, expansion, and disambiguation of acronyms in biomedical texts." International Symposium on Parallel and Distributed Processing and Applications. Springer, Berlin, Heidelberg, 2005.

### CSV row 21

Resource: (not supplied). Year: 2005. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Nadeau, D., & Turney, P.D. (2005). A supervised learning approach to acronym identification. In Balázs Kégl & G. Lapalme (Eds.), Advances in artificial intelligence. Proceedings of the 18th Conference of the Canadian Society for Computational Studies of Intelligence, Canadian AI 2005. (LNCS 3501) (pp. 319–329). Heidelberg, Germany: Springer.

### CSV row 22

Resource: (not supplied). Year: 2005. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: https://academic.oup.com/bioinformatics/article/21/18/3658/202307

Resource navigation: Not supplied. Paper: [link](https://academic.oup.com/bioinformatics/article/21/18/3658/202307).

Citation: Gaudan, Sylvain, Harald Kirsch, and Dietrich Rebholz-Schuhmann. "Resolving abbreviations to their senses in Medline." Bioinformatics 21.18 (2005): 3658-3664.

### CSV row 23

Resource: (not supplied). Year: 2005. Notes: Review.

Resource URL field: (not supplied)

Paper URL field: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC540091/

Resource navigation: Not supplied. Paper: [link](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC540091/).

Citation: (not supplied)

### CSV row 24

Resource: Database:SaRAD. Year: 2004. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Adar E SaRAD: a Simple and Robust Abbreviation Dictionary. Bioinformatics. 2004 Mar 1; 20(4):527-33.

### CSV row 25

Resource: (not supplied). Year: 2003. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: H. Liu, C. Friedman, "Mining Terminological Knowledge in Large Biomedical Corpora", Proceedings of the Pacific Symposium on Biocomputing, vol. 8, pp. 415-426, 2003.

### CSV row 26

Resource: Tool: ExtractAbbrev / Schwartz & Hearst. Year: 2003. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: (not supplied)

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: Not supplied.

Citation: A.S. Schwartz, M.A. Hearst, "A simple algorithm for identifying abbreviation definitions in biomedical text", Proceedings of the Pacific Symposium on Biocomputing, vol. 8, pp. 451-462, 2003.

### CSV row 27

Resource: Corpus: Schwartz & Hearst. Year: 2003. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: (not supplied)

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: Not supplied.

Citation: A.S. Schwartz, M.A. Hearst, "A simple algorithm for identifying abbreviation definitions in biomedical text", Proceedings of the Pacific Symposium on Biocomputing, vol. 8, pp. 451-462, 2003.

### CSV row 28

Resource: Database:Stanford Biomedical Abbreviation Server. Year: 2002. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: J.T. Chang, H. Schütze, R.B. Altman, "Creating an Online Dictionary of Abbreviations from MEDLINE", The Journal of the American Medical Informatics Association, vol. 9, pp. 612-620, 2002.

### CSV row 29

Resource: Tool:AbbRE. Year: 2002. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: H. Yu, G. Hripcsak, C. Friedman, "Mapping abbreviations to full forms in biomedical articles", Journal of the American Medical Informatics Association, vol. 9, pp. 162-172, 2002.

### CSV row 30

Resource: Corpus:Medstract. Year: 2002. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: J. Pustejovsky, J. Castano, R. Sauri, A. Rumshinsky, J. Zhang, and W. Luo. 2002. Medstract: creating large-scale information servers for biomedical libraries. In Proceedings of the ACL-02 workshop on Natural language processing in the biomedical domain-Volume 3, pages 85–92. Association for Computational Linguistics.

### CSV row 31

Resource: Database:ARGH. Year: 2002. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: https://www.ncbi.nlm.nih.gov/pubmed/12501816

Resource navigation: Not supplied. Paper: [link](https://www.ncbi.nlm.nih.gov/pubmed/12501816).

Citation: Wren JD, Garner HR Heuristics for identification of acronym-definition patterns within text: towards an automated construction of comprehensive acronym-definition dictionaries. Methods Inf Med. 2002; 41(5):426-34.

### CSV row 32

Resource: Corpus:Medstract. Year: 2001. Notes: (none).

Resource URL field: http://bioc.sourceforge.net/

Paper URL field: (not supplied)

Resource navigation: [link](http://bioc.sourceforge.net/). Paper: Not supplied.

Citation: Pustejovsky J. Castano J. Cochran B. et al.  . ( 2001 ) Automatic extraction of acronym-meaning pairs from MEDLINE databases . Stud. Health Technol. Inform.  , 84 , 371 – 375 .

### CSV row 33

Resource: Database:AcroMed. Year: 2001. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Pustejovsky J, Castaño J, Cochran B, Kotecki M, Morrell M Automatic extraction of acronym-meaning pairs from MEDLINE databases. Stud Health Technol Inform. 2001; 84(Pt 1):371-5.

### CSV row 34

Resource: Tool:Acrophile. Year: 2000. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: L. Larkey, P. Ogilvie, A Price, B. Tamilio, "Acrophile: An Automated Acronym Extractor and Server", Proceedings of the ACM Digital Libraries Conference, pp. 205-214, 2000.

### CSV row 35

Resource: (not supplied). Year: 2000. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Yoshida M, Fukuda K, Takagi T: PNAD-CSS: a workbench for constructing a protein name abbreviation dictionary. Bioinformatics 2000, 16(2):169–175. 10.1093/bioinformatics/16.2.169

### CSV row 36

Resource: (not supplied). Year: (not supplied). Notes: Review of clinical acronyms.

Resource URL field: (not supplied)

Paper URL field: https://dash.harvard.edu/bitstream/handle/1/27822158/4930590.pdf?sequence=1

Resource navigation: Not supplied. Paper: [link](https://dash.harvard.edu/bitstream/handle/1/27822158/4930590.pdf?sequence=1).

Citation: (not supplied)

### CSV row 37

Resource: (not supplied). Year: 2022. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Veyseh, Amir Pouran Ben, et al. "Acronym Extraction and Acronym Disambiguation Shared Tasks at the Scientific Document Understanding Workshop." (2022).

### CSV row 38

Resource: Tool: MadDog. Year: 2021. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Amir Pouran Ben Veyseh, Franck Dernoncourt, Walter Chang, and Thien Huu Nguyen. 2021. MadDog: A Web-based System for Acronym Identification and Disambiguation. In Proceedings of the 16th Conference of the European Chapter of the Association for Computational Linguistics: System Demonstrations, pages 160–167, Online. Association for Computational Linguistics.

### CSV row 39

Resource: Corpus: Acronym Identification. Year: 2020. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Amir Pouran Ben Veyseh, Franck Dernoncourt, Quan Hung Tran, and Thien Huu Nguyen. 2020. What Does This Acronym Mean? Introducing a New Dataset for Acronym Identification and Disambiguation. In Proceedings of the 28th International Conference on Computational Linguistics, pages 3285–3301, Barcelona, Spain (Online). International Committee on Computational Linguistics.

### CSV row 40

Resource: Tool: DECBAE. Year: 2019. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Qiao Jin, Jinling Liu, and Xinghua Lu. 2019. Deep Contextualized Biomedical Abbreviation Expansion. In Proceedings of the 18th BioNLP Workshop and Shared Task, pages 88–96, Florence, Italy. Association for Computational Linguistics.

### CSV row 41

Resource: Corpus, Clinical. Year: (not supplied). Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: Zhi Wen, Xing Han Lu, and Siva Reddy. 2020. MeDAL: Medical Abbreviation Disambiguation Dataset for Natural Language Understanding Pretraining. In Proceedings of the 3rd Clinical Natural Language Processing Workshop, pages 130–135, Online. Association for Computational Linguistics.

### CSV row 42

Resource: Tool: BLAR. Year: 2021. Notes: (none).

Resource URL field: (not supplied)

Paper URL field: (not supplied)

Resource navigation: Not supplied. Paper: Not supplied.

Citation: William Hogan, Yoshiki Vazquez Baeza, Yannis Katsis, Tyler Baldwin, Ho-Cheol Kim, and Chun-Nan Hsu. 2021. BLAR: Biomedical Local Acronym Resolver. In Proceedings of the 20th Workshop on Biomedical Language Processing, pages 126–130, Online. Association for Computational Linguistics.

