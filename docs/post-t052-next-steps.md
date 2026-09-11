# Practical next steps after T052

Planning date: September 10, 2026. Status: task descriptions prepared for future assignment; implementation and new annotation have not started.

## Direction

Keep document-local abbreviation-definition extraction as the practical core. Record neighboring naming/code relations and difficult evidence without forcing them into exact SF/LF pairs. Test whether available methods recover useful additional definitions before investing in fusion, iterative denoising or broader interpretive grounding.

This plan operationalizes the user's accepted next-step discussion. It supersedes the older roadmap's immediate execution order for this milestone, not its historical records or settled scientific contracts. It does not authorize Luna to execute all tasks automatically. Assign one Luna task at a time; human steps are explicit dependencies.

Evidence: [frozen T052 bundle](../evidence/T052/README.md), [initial scientific model](scientific-model/2026-09-10-interpretive-grounding.md), [historical T031 comparison](tasks/completed/T031-comparative-benchmark-and-oracle-analysis.md), and [September 8 audit](project-status-review-2026-09-08.md). Historical comparison gains do not establish contemporary complementarity. T052's completed assisted annotations do not certify exhaustive independent gold.

## Ownership and task sequence

Each task file includes dependencies, bounded steps, acceptance evidence and a stopping point. **You** means the scientific lead performs the judgments or decisions. **Luna** means implementation, preparation, validation or reporting.

| [T053](tasks/T053-t052-audit-inventory.md) | **Luna** | Build the targeted T052 audit inventory |
| [T054](tasks/T054-audit-supplement-contract.md) | **Luna** | Add a versioned audit supplement contract |
| [T055](tasks/T055-assisted-audit-reviewer.md) | **Luna** | Deliver the assisted audit review interface |
| [T056](tasks/T056-human-t052-adjudication.md) | **You** | Adjudicate the T052 audit and provisional distinctions |
| [T057](tasks/T057-freeze-development-guidelines.md) | **Luna** | Freeze the development guidelines and challenge views |
| [T058](tasks/T058-bounded-runtime-readiness.md) | **Luna** | Verify existing baseline runtimes within a repair budget |
| [T059](tasks/T059-bounded-language-model-adapter.md) | **Luna** | Prepare one evidence-grounded language-model extraction baseline |
| [T060](tasks/T060-development-method-run.md) | **Luna** | Run the bounded development comparison and build an output review packet |
| [T061](tasks/T061-human-development-output-review.md) | **You** | Adjudicate new method outputs on development passages |
| [T062](tasks/T062-development-readout-and-protocol.md) | **Luna** | Measure recoverable misses and draft a fresh-sample protocol |
| [T063](tasks/T063-human-protocol-decision.md) | **You** | Choose the fresh-check scope and success criteria |
| [T064](tasks/T064-prediction-blind-review-mode.md) | **Luna** | Add a genuinely prediction-blind annotation mode |
| [T065](tasks/T065-fresh-sample-and-blind-packet.md) | **Luna** | Freeze the protocol and prepare the fresh annotation packet |
| [T066](tasks/T066-human-blind-annotation.md) | **You** | Annotate the fresh passages before seeing predictions |
| [T067](tasks/T067-fresh-evaluation-readout.md) | **Luna** | Run the frozen comparison and report the fresh-check result |
| [T068](tasks/T068-human-next-direction.md) | **You** | Choose the next project milestone from the evidence |

Recommended handoff order:

1. Luna T053 → T054 → T055; then **you T056**.
2. Luna T057 → T058 → T059 → T060; then **you T061**.
3. Luna T062; then **you T063**.
4. Luna T064 → T065; then **you T066**.
5. Luna T067; then **you T068**.

T058 readiness work can run while annotation is pending. T064 can be implemented with fixtures after T055/T057 while protocol decisions are pending. These are scheduling options, not permission to spawn agents or run several assignments together. T059 can develop the adapter against T054 fixtures but must use T057 before freezing the real prompt.

There are eleven Luna assignments and five user steps. The frontend work is deliberately separated into assisted review (T055) and prediction-blind review (T064). T060 reuses the assisted interface; it should need packet preparation, not another application.

## What each phase decides

### A. Audit and stabilize the development task — T053–T057

Use a bounded subset of T052 to resolve concrete questions. Do not relabel every observation into the full interpretive-grounding taxonomy. The immediate questions are support, relation kind, evidence structure, source errors and required context.

The 26 additions and six corrected suggestion dispositions are not 32 distinct cases. Select their enclosing passages, deduplicate and preserve reasons. Half of the additions occur in two lipid passages from one article. This concentration is useful for challenge construction but is not a population estimate.

The suspected 2A relation, missing HDL occurrences and tcP/shared-evidence questions are unadjudicated observations from the discussion. Luna must prepare them for the user, not silently alter the frozen evidence.

### B. Measure what the existing methods can recover — T058–T062

Compare identical development inputs using S&H, available Ab3P/PLODv2 and one bounded language-model baseline. Keep detector coverage, pairing, exact boundaries, task scope and representational limitations separate.

The central questions are: what additional supported relations enter the candidate pool, what errors come with them, and whether those gains justify processing and review cost. Gold-assisted union is an upper bound for those candidates, not a deployable system. Agreement between tools is not independent truth.

This phase may recommend a new narrowly scoped candidate generator or selector, but implementing one needs a new task before freezing the fresh check. The current plan does not hide an entire research-method development project inside a comparison task.

### C. Check a frozen choice on fresh material — T063–T068

The proposed starting budget is 24 passages from at least 12 new article groups, balanced between abstract and PMC text arms, with at most two passages per group. This is a proposal for T063, not an approved population definition, split or powered sample-size claim. Luna must present concrete tolerances and acquisition limits for that decision.

Sample independently of detector output, including passages that may contain no definitions. Exclude all discovery article groups and linked counterparts. Freeze method/prompt/config before acquisition. Use development/synthetic text for software QA; keep actual fresh annotations prediction-blind until locked.

A small fresh check can support a practical next decision while remaining inconclusive about broad superiority. A strong single baseline is an acceptable outcome. Additional data collection must be a new explicit protocol, not repeated sampling until a desired result appears.

## Common engineering requirements for Luna

- Read AGENTS.md, START_HERE_FOR_CODEX.md, the assigned file, [Luna's guide](tasks/LUNA_EXECUTION_GUIDE.md) and relevant dependency outputs. Verify current code and artifacts; dated completion notes are not runtime checks.
- Reuse the modular monolith, typed boundaries, registries/YAML selection and existing persistence/evaluation machinery. Keep scientific models separate from filesystem/UI/worker implementations. Do not build a new generic framework.
- Relevant starting points: `src/abrex/literature/review_models.py`, `review_packet.py`, `review.py`, `reviewer_ui.py`, `review_interchange.py`, `pilot_methods.py`, `pilot_sampling.py`, `pilot_sources.py`; `src/abrex/corpora/annotation_pilot.py`; `src/abrex/evaluation/comparative.py`; resolver adapters and `scripts/run_t052_reviewer.py`. Inspect functions on demand; do not assume a new module is necessary.
- Preserve old packet/import behavior and exact half-open Unicode source offsets. A multi-fragment evidence list is not a contiguous expansion, and a reconstructed interpretation has no invented source span.
- Keep unsupported, uncertain, unreviewed, out-of-scope, incomplete, processing-failed and unscoreable states distinct. Failure cannot become a clean negative. Scope/eligibility policies must not discard inconvenient predicted false positives.
- Preserve every frozen bundle. Corrections use a new version linked by hashes. Durable annotations include revision history, exposure/provenance and packet identity. Changes to text/config/model invalidate dependent caches.
- Use local bounded execution, no publication or broad acquisition. Reuse authorized credentials/routes without asking again; obtain missing essential route/budget decisions only when actually needed. No optional tool is a reason to reopen the settled BADREX exclusion.
- Do not label engineering complete as scientifically validated. A skipped required real run leaves operational acceptance pending; an unavailable optional method limits the comparison rather than generating invented results.

## Frontend acceptance contract

T055 and T064 contain explicit interaction requirements. A readable report, mocked screenshot or successful HTTP request does not satisfy an annotation-interface task.

Use the current reviewer stack, and read the applicable frontend testing/debugging skill when implementing or testing it. Keep technical diagnostics outside the main annotation flow. Every user handoff must include an actual working local page, exact launch instructions, packet and save paths, plain-language controls, backup/restore and tested progress persistence.

Use disposable QA annotations for browser tests. Verify real selection/edit/add/save/reload/import, repeated strings, supplementary Unicode, uncertainty and small-screen layout. Never test by mutating frozen evidence or by annotating the fresh evaluation packet. If browser tools are unavailable, finish independent work and explicitly leave browser acceptance pending; do not hand off a supposedly verified UI.

Blindness must be enforced in supplied data and server responses, not just in visible controls. No evaluated outputs may reach the blind page. Locking must record provenance and prevent silent replacement; later edits are separate versions.

## Common validation and handoff

Each Luna task requires its focused regression/contract checks and the canonical repository fast gate:

```powershell
.\env313\Scripts\python.exe scripts/quality_gate.py --python .\env313\Scripts\python.exe
git diff --check
```

Run these commands separately. Use the documented equivalent runtime if necessary. At T067 also run the full gate with `--full`. Do not lower coverage or change exclusions to make it pass. Report current failures accurately, separating pre-existing issues from introduced regressions.

For documentation-only work, check links, task IDs, dependency ordering and required sections as well as the fast gate. Human annotation steps do not require the user to run software checks; Luna validates submitted artifacts in the next assigned implementation task.

Write completion/progress notes with actual artifact paths, commands, hashes, checks, readiness and the next dependency. Do not create a completion note for a user step until the user has actually returned the requested work. A practical outcome may be an explicitly incomplete optional runtime plus usable independent deliverables, but do not claim its missing scientific result.

Every user handoff must say:

- what the user needs to do and approximately how many passages/proposals;
- how to open, pause, save and return work;
- which decisions remain uncertain;
- what Luna will do after the user returns it.

## Assigning the first task

> Implement T053 from docs/tasks/T053-t052-audit-inventory.md. Follow docs/post-t052-next-steps.md and docs/tasks/LUNA_EXECUTION_GUIDE.md. Deliver only this bounded task, run its checks and the fast gate, and record actual outputs. Do not proceed to T054 or perform the user's annotation.

Assign subsequent Luna tasks the same way with the correct identifier. This planning work creates files only; it does not create app tasks, dispatch Luna or start experiments.
