# T029 completion note: contemporary sampling and article-level data separation

Status: Complete for the bounded proposal mechanism and local pilot. Scientific
approval of the final production mix, target years and role sizes remains open.

## Delivered

- Added typed frame, role and proposal configuration plus deterministic
  identifier/content/near-duplicate grouping in
  `src/abrex/literature/sampling.py`.
- Added official-split preservation, unavailable-text accounting,
  teacher-overlap accounting and explicit challenge-vs-random assignments.
- Added `derive_lexicon_view`, which exposes only occurrence links from roles
  explicitly marked `lexicon_allowed`; evaluation/challenge evidence is not
  available through that view.
- Added optional T028 aggregate-frequency lookup for sampled occurrence
  priorities. Aggregate counts remain distinct from article locations,
  document frequency and labels.
- Added the `abrex literature sample` CLI command, YAML example, small JSONL
  fixture and public documentation in
  [sampling-and-leakage.md](../../sampling-and-leakage.md).

## Evidence and artifacts

The five-record local pilot produced four article groups: the PMID/PMCID rows
were kept together, one text was unavailable, one tagged full-text challenge
group was selected separately, and one allowed `CNS` occurrence link received
the T028 pilot aggregate priority 120,393. The generated manifest fingerprint
was `96ee5a0951272208a7a372e4300e5fde88615398c023718452e9b5433501a44d` at the
time of recording. The report is
[T029-sampling-pilot-report.json](../../artifacts/T029-sampling-pilot-report.json);
the raw manifest remains ignored under `.artifacts/T029/`.

Earlier accepted T025--T028 pilots supply the retained real-source hashes in
that report. They support provenance wiring only; they do not make this small
fixture representative or unbiased.

## Verification

- Focused T029 suite: `10 passed`.
- Determinism, duplicate/version grouping, held-out lexicon exclusion,
  official-split preservation, accounting and conflicting-split rejection are
  covered.
- The task-wide fast and full repository gates are recorded below after the
  final documentation pass.

## Open decisions and limitations

- Scientific review must choose the target years, abstract/full-text mix,
  strata, sample sizes and final split rationale.
- T047 must freeze the work-scale discovery/training population separately;
  this task deliberately does not select it.
- Teacher-training overlap is unknown for the local frame and must be audited
  where source/model manifests allow it.
- No Ab3P-only sample is presented as an unbiased benchmark.

## Next ready task

T030 is ready: create the auditable contemporary annotation pilot using this
proposal mechanism. T046 (external dictionary acquisition) is also independent
and ready after T028; T047 becomes ready after this task and should finalize
the large-scale selection before T042.
