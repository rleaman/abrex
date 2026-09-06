# This file contains notes and links to keep track of which may be useful later

## Datasets:
- The SDU@AAAI-21 datasets at https://github.com/amirveyseh/AAAI-21-SDU-shared-task-1-AI and https://github.com/amirveyseh/AAAI-21-SDU-shared-task-2-AD.
- The official SDU@AAAI-22 AE dataset at https://github.com/amirveyseh/AAAI-22-SDU-shared-task-1-AE/
- BIOADI corpus at http://sourceforge.net/projects/bioc/files/BioADI-BioC.zip/download
- The Schwartz & Hearst / BioText corpus at http://sourceforge.net/projects/bioc/files/SH-BioC.zip/download and a version corrected for BADREX at https://github.com/downloads/philgooch/BADREX-Biomedical-Abbreviation-Expander/yeast_abbrev_labeled.xml.
- The Ab3P corpus at http://sourceforge.net/projects/bioc/files/Ab3P-BioC.zip/download
- The MEDSTRACT corpus at http://sourceforge.net/projects/bioc/files/MEDSTRACT.zip/download and a version corrected for BADREX at https://github.com/downloads/philgooch/BADREX-Biomedical-Abbreviation-Expander/medstract_corrected_pairs.txt.

## Systems:
- Ab3P at https://bioc.sourceforge.net/, specifically one of the many tools distributed in http://sourceforge.net/projects/bioc/files/BioC_C%2B%2B_1.1.tar/download
- BADREX at https://github.com/philgooch/BADREX-Biomedical-Abbreviation-Expander
- Auto-CORPus, described in https://pmc.ncbi.nlm.nih.gov/articles/PMC8885717, distributed at https://github.com/omicsNLP/Auto-CORPus
- scispacy has an implementation of Schwartz & Hearst, 2003: https://github.com/allenai/scispacy/blob/main/scispacy/abbreviation.py
- MadDog system: https://github.com/amirveyseh/MadDog

## Resources:
- Medical Abbreviation and Acronym Meta-Inventory: https://github.com/lisavirginia/clinical-abbreviations


## Unavailable:
BioAbbreviate corpus in the recent BioAbbreviate paper (https://hal.science/hal-05637071/) says it is available on GitHub (https://github.com/mouhebmhd/BioAbbreviate-A-Biomedical-Dataset-for-Abbreviation-Expansion-and-Disambiguation-), but the repo only has a README

## PLODv2 error analysis

### Examples found to be correct:
- Extra chars at end of lf: "long terminal repeat, (LTR)"
- Extra chars at end of lf: "kainic acid- (KA)"
- Extra chars at end of sf, separated by slash: "macrophage-related protein-8 (MRP8/ S100A8)"
- Missed closing paren at end of lf: "poly(dimethylsiloxane) (PDMS)"
- Missed the same text ending at end of both lf and sf: "peroxisome proliferator-activated receptor gamma (PPAR gamma)"
- Missed the same text ending at end of both lf and sf: "ionized calcium-binding adapter molecule 1+ (IBA1+ )"
- Missed the same text ending at end of both lf and sf: "prostaglandin E(2) (PGE(2))"

### Examples found to be wrong:
Any pairs found in a title; so far, all of these are not good abbr pairs
