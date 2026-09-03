# Numbered Codex Assignments

## How to use these tasks

The user can assign work by saying, for example, `Implement T006` or `Take T003 and T004`.

Before starting any task, Codex must read:

- `AGENTS.md`;
- `START_HERE_FOR_CODEX.md`;
- the assigned task;
- any dependencies listed in that task;
- relevant architecture/scientific docs.

Do not treat task numbering as permission to ignore dependencies.

## Task map

| Task | Title | Depends on | Research oversight |
| --- | --- | --- | --- |
| T000 | Bootstrap repository | none | low |
| T001 | Config and registry infrastructure | T000 | low |
| T002 | Core domain schema and provenance | T000 | medium |
| T003 | Corpus adapter framework | T001, T002 | low/medium |
| T004 | Canonical validation and serialization | T002, T003 | medium |
| T005 | Resolver interface and execution contract | T001, T002 | low |
| T006 | Evaluation matching engine | T002, T004 | high on semantics, low on implementation |
| T007 | Ab3P baseline adapter | T005 | low |
| T008 | Regression/golden baseline suite | T004, T006, T007 | medium |
| T009 | Error-analysis/reporting framework | T006 | low/medium |
| T010 | Experiment runner and reproducibility | T001, T004, T005, T006 | low |
| T011 | Historical corpus adapters | T003, T004 | medium |
| T012 | Schwartz-Hearst baseline | T005, T008 | medium |
| T013 | Candidate-generation framework | T001, T002, T008 | medium/high |
| T014 | Feature extraction framework | T001, T013 | medium |
| T015 | Learned scorer/ranker scaffold | T010, T013, T014 | high |
| T016 | PMC/PubMed production adapter | T005, T010 | medium |

## Recommended waves

### Wave A - substrate
T000 through T010, with T006 scientific semantics reviewed by the user.

### Wave B - benchmark breadth
T011 and T012.

### Wave C - new-method research
T013 through T015.

### Wave D - production integration
T016.
