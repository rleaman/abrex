# Abrex project status and findings before the October 2026 campaign

Abrex is a research and engineering project for identifying abbreviation
meanings in biomedical literature and turning those findings into reusable,
traceable data. Its core unit is a relation between a short form and the long
form that an article uses to define it, together with the exact supporting text.
For example, an extractor should recognize the definition in "interleukin 2
(IL-2)" and retain where both expressions occur in the source.

The project combines an experimental platform with a longer-term method and
resource development effort. The platform lets researchers ingest literature,
run interchangeable extraction methods, inspect disagreements, collect human
judgments, and compare results under shared evaluation rules. It provides the
means to investigate which methods work, where they fail, and whether proposed
improvements survive evaluation on new articles.

## Project purpose

The purpose is to make abbreviation handling a reliable, scalable component of
biomedical text processing, supporting downstream systems that need to connect
an author's shortened expressions with their intended concepts. The intended
solution should be practical for large literature collections, with automation
handling routine preparation and analysis and the scientist concentrating on
substantive judgments.

The central research hypothesis is that extraction tools, abbreviation
lexicons and the literature itself provide complementary, noisy evidence that
can help improve one another. Candidate definitions gathered from articles may
support new contextual patterns, better training data and richer dictionaries;
those resources may then improve subsequent extraction. Whether this iterative
process improves accuracy is an empirical question. Agreement between related
sources alone does not establish correctness. The intended contributions are
better extraction methods and reusable literature and dictionary resources.
[Original project concept](../handoff/idea.txt),
[platform architecture](architecture.md).

## Research scope and implemented capabilities

The practical task is extracting document-local short-form/long-form definition
relations from biomedical abstracts and full text, including textual tables and
lists. Undefined-acronym sense disambiguation, global dictionary lookup and
article-wide mention propagation are distinct tasks. The broader project aims
also include a tagged literature corpus, an expanded dictionary with supporting
contexts and frequencies, and improved extraction through combined evidence.

Implemented capabilities include typed domain models and configuration,
registry-based components, corpus adapters, exact-pair and span evaluation,
prediction caching, reproducibility manifests, source-text provenance,
PubMed/BioC/JATS ingestion, structure-aware representations, assisted and blind
annotation interfaces, and portable Linux execution. Ab3P and PLODv2 completed
real Linux jobs; historical runtime-configuration failures do not establish that
these tools are unavailable. Software and runtime readiness are separate from
scientific accuracy.

## What CellLiteraturePipeline contributes

Abrex's sister project, CellLiteraturePipeline (CLP), also implements some
abbreviation handling. CLP's full V5.1 table/list system handles substantially more 
than two-column tables: it includes alternating passages, delimited and inline lists, recovery rules, orientation and section boundaries, and selective Jev decisions.

Its October 2 saved evaluation contains 200 sections with 4,035 annotated pair
occurrences: 143 positive sections, 50 negative sections and seven requiring
parser extension. Document-unique normalized pair precision was 99.35%, recall
98.44%, and F1 98.89%. These are development/calibration results on a risk-stratified
sample. Normalization and document-level deduplication differ from Abrex's exact
occurrence/offset metric; the figures cannot be directly compared with the Abrex
results reported here.
[CLP evaluation](../../CellLiteraturePipeline/experiments/abbreviations/evaluations/abbr-v5-validation-v1.0.0__v5.1-live-t052/summary.json).

CLP's production summary records 105,233 article records, 105,134 unique articles,
and 174,761 accepted pair outputs. This establishes processing scale and yield;
those outputs are not 174,761 independently verified gold annotations.
[CLP production summary](../../CellLiteraturePipeline/experiments/abbreviations/reports/abbr-full-table-annotations-v5.1/summary.json).

At the Abrex cutoff, a pinned CLP annotation snapshot contained 3,696 pairs with
unique exact mappings and 339 unscorable mappings. Abrex's CLP-derived generator
was a narrow two-column implementation rather than the full CLP system. Abrex had
not independently measured the complete parser's precision, recall or F1. The
full transfer and compatible evaluation were therefore an important outstanding
experiment. These cutoff counts refer to the snapshot in the reference commit;
the current working snapshot may contain later campaign corrections.
[Contemporaneous integration description](archive/planning/revival-handoff-2026-10-02.md).

## Evidence cutoff and overall assessment

Status cutoff: October 5, 2026, after the T068 scientific decision and before
implementation of `experiment-campaign-2026-10`. Prepared October 6 for use in
a separate research discussion. The Abrex reference commit is
`5fcf3a7a467059a9d226a3e74ac721b6d022f8ac`. This is a historical evidence summary,
not a current work assignment. Subsequent campaign results are excluded.

Abrex has a functioning experimental platform, traceable human annotations,
real baseline comparisons, and a useful negative result from a small blind
evaluation. It has not demonstrated a generally superior contemporary biomedical
abbreviation extractor. Ab3P remains the operational incumbent for continuity;
its contemporary superiority has not been established. The sister project,
CellLiteraturePipeline (CLP), has substantially stronger table/list extraction
evidence than the narrow CLP-derived component then present in Abrex.

## Historical baseline comparison

The bounded historical comparison used 64 Ab3P-corpus documents with 143 gold
pairs and exact-pair matching.

| Method | True positives | False positives | False negatives | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ab3P with native offsets | 121 | 4 | 22 | 0.968 | 0.846 | 0.903 |
| Schwartz-Hearst | 110 | 5 | 33 | 0.957 | 0.769 | 0.853 |
| PLODv2 pairing | 104 | 20 | 39 | 0.839 | 0.727 | 0.779 |

Ab3P performed best on this slice. Gold-assisted union recall across the three
methods was 130/143, or 0.909; that is an oracle ceiling, not an executable
ensemble's accuracy. A tested two-resolver union added three true positives and
four false positives over Ab3P, producing F1 0.902 and no supported improvement.
[Historical comparison](artifacts/T031-comparative-analysis-report.core.json),
[hybrid report](artifacts/T032-transparent-hybrid-report.json).

Structural-prose and bounded lexical candidate additions did not improve recall
on this slice. The slice lacked the JATS structure metadata needed to evaluate
table extraction, so these results do not establish that structural or lexical
methods are ineffective on appropriate material.
[Structural evidence](tasks/completed/T033-structural-candidate-generators.md),
[lexical evidence](tasks/completed/T034-lexical-candidates-and-evidence-features.md).

## Assisted contemporary development results

The revised development view contains 20 passages and 67 strict exact relations,
including eight added during follow-up adjudication. It is diagnostically
selected, assisted development evidence, not an independent population sample.

| Method | True positives | False positives | False negatives | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ab3P | 35 | 12 | 32 | 0.745 | 0.522 | 0.614 |
| Schwartz-Hearst | 36 | 6 | 31 | 0.857 | 0.537 | 0.661 |
| PLODv2 pairing | 34 | 1 | 33 | 0.971 | 0.507 | 0.667 |
| Jev candidate judge | 25 | 11 | 42 | 0.694 | 0.373 | 0.485 |
| Schwartz-Hearst plus PLOD exact union | 45 | 7 | 22 | 0.865 | 0.672 | 0.756 |

Predictions matching explicitly classified relations outside the strict target
are accounted for separately rather than included in these false-positive counts.
The union added nine correct strict relations and one false positive over
Schwartz-Hearst, motivating a frozen fresh test.
[Revised development readout](artifacts/T062-development-readout.md).

Earlier reports use a 59-pair version of these passages and must not be mixed
with the 67-pair results. On the earlier version, Jev's candidate pool contained
47/59 gold pairs, a 79.7% recall ceiling before judgment. Jev judged validity and
orientation over supplied candidates; it did not perform direct extraction of
arbitrary new pairs. Its disappointing results therefore do not settle the value
of source-grounded LLM extraction.
[Earlier Jev experiment](artifacts/T059-jev-split-development.json).

## Prediction blind fresh evaluation

The fresh check used 32 passages from eight new linked article groups: 24 prose
passages and eight table/list passages. One human reviewer completed annotation
before evaluated predictions were exposed. The corrected annotation lock
contained 32 strict relations and eight diagnostic relations. Only seven
passages contained strict gold pairs; the other 25 were empty under that target.

| Method | True positives | False positives | False negatives | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Schwartz-Hearst | 6 | 10 | 26 | 0.375 | 0.188 | 0.250 |
| PLODv2 pairing | 18 | 14 | 14 | 0.563 | 0.563 | 0.563 |
| Schwartz-Hearst plus PLOD exact union | 20 | 20 | 12 | 0.500 | 0.625 | 0.556 |

The registered comparison was the exact union against Schwartz-Hearst. Its
adoption rule required improved strict-pair F1, at least three unique correct
additions, at most two additional false positives, and zero runtime failures.
The union failed: it added 14 correct pairs but also ten false positives.
Both underlying jobs completed all 32 inputs without runtime failure.

All 14 correct additions came from one article group. Prose F1 decreased from
0.500 to 0.480, while table/list F1 increased from 0.125 to 0.596. PLOD alone
had the strongest standalone numerical result, but this small, clustered sample
does not establish broad superiority. Ab3P and Jev were not evaluated on this
fresh sample. No population weighting or inferential confidence interval was
claimed. [Complete fresh readout](artifacts/T067-fresh-evaluation-readout-v1.json).

The final scientific decision rejected adoption of the tested fixed union and
did not accept any current method as a sufficiently accurate modern solution.
Ab3P remained the pragmatic incumbent. The short T067 Markdown report's sentence
recommending retention of Schwartz-Hearst is superseded as an operational
recommendation by this later decision; the frozen numerical results stand.
[T068 decision](tasks/T068-human-next-direction.md).

## Scientific lessons and unresolved questions

Human annotation established useful distinctions between strict abbreviations,
other naming/code relations, source errors and discontinuous evidence. Some real
relations cannot be represented faithfully as one contiguous exact pair. Supported
neighboring relations, uncertain cases and unsearched passages must not silently
become negative examples. Exact source evidence and reconstructed interpretation
need separate representations.
[Scientific model](scientific-model/2026-09-12-development-challenge.md).

The results establish bounded method behavior and reject one proposed fixed
combination. They do not establish a general winner or disprove selective,
learned, structural or generative approaches. Differences across the historical,
assisted and fresh datasets are not a controlled measure of temporal performance
decline. Candidate coverage, representation, scoring scope and sample composition
all affect the observed scores.

The next research questions identified at the cutoff were:

1. How does the complete CLP system transfer under explicitly reconciled metrics,
   and how much does it add on fresh structured passages?
2. How does the operational incumbent Ab3P perform on the same contemporary
   inputs as the alternatives?
3. Which failures arise from missing candidates, source/structure mapping,
   boundaries, orientation, pairing or acceptance? How much could better pairing
   recover from retained PLOD spans without changing detection?
4. Can direct source-grounded LLM extraction recover pairs that candidate judging
   never receives, while controlling false positives and unsupported output?

These questions became the October campaign's selected experiments. The larger
tagged corpus and expanded dictionary, a validated iterative-learning campaign,
and a real downstream impact evaluation remained unfinished at this cutoff.
Existing scorer and downstream interfaces were not evidence of scientific gains.
[Scorer limitations](tasks/completed/T038-lightweight-scorer-training.md),
[downstream limitations](tasks/completed/T044-downstream-impact-evaluation.md).

This report contains the context and principal numbers needed for a standalone
ideation discussion. Relative links identify repository provenance; they require
the corresponding repositories to resolve. For status after this historical
cutoff, consult [current work](CURRENT_WORK.md).
