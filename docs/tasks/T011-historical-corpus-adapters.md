# T011 - Historical Corpus Adapters

## Goal

Add real corpus adapters for the established abbreviation-definition datasets selected by the user, while preserving source variants and corrections distinctly.

## Depends on

T003, T004.

## Initial targets

Implement adapters incrementally for datasets such as:

- Schwartz & Hearst / BioText;
- corrected BADREX variant where available;
- Ab3P corpus;
- MEDSTRACT and any corrected variant supplied by the user;
- BIOADI;
- SDU@AAAI-21 abbreviation identification/definition datasets;
- SDU@AAAI-22 data selected by the user.

Do not assume all target downloads or licenses permit automatic redistribution. Adapters should operate on user-supplied/downloaded source files when needed.

## Requirements

Each adapter gets:

- a stable dataset/adapter key;
- source-format documentation;
- provenance preservation;
- validation summary;
- small checked-in fixture derived only when licensing permits, otherwise synthetic structural fixture;
- adapter-specific tests;
- explicit dataset-variant naming.

## Acceptance criteria

Each implemented adapter can build a canonical artifact and manifest through the common corpus build pipeline with no dataset-specific evaluator code.
