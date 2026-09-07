# T018 Build and verify real Ab3P in the existing Ubuntu environment

Status: Complete. Assigned implementer: GPT-5.6 Luna. Milestone: A.

## Outcome

Produce a reproducible, tested Ab3P installation and an installation manifest without changing its detection algorithm.

## Dependencies and reading

[T017](T017-reproducible-development-environments.md)

Read [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [completion plan](../project-completion-plan.md), [state audit](../project-state-audit.md), AGENTS.md and START_HERE_FOR_CODEX.md. Then inspect: ../NCBITextLib/README.md; ../NCBITextLib/lib/Makefile; ../Ab3P/README.md; ../Ab3P/Makefile; ../Ab3P/lib/Makefile; ../Ab3P/path_Ab3P; docs/resolvers.md.

Dependencies mean the relevant accepted artifacts exist, not merely that a completion note exists. Work only on this assigned task.

## Implementation steps

1. Use the existing Ubuntu WSL2 environment first: g++, make, python3 and git were detected during planning. Inventory versions and disk paths; do not assume its Python already meets the core target.
2. Use the user-supplied sibling ../NCBITextLib first. Verify its source revision or tree hash and required headers/build files, then copy/build it with Ab3P in a task-owned writable build directory. Preserve both supplied source copies; retain all build commands and minimal compatibility patches. Download only if a specific missing dependency requires it.
3. Run the upstream make test comparison against identify_abbr-out. Add a small non-ASCII and multiline smoke input and inspect raw outputs.
4. Document a Windows launch example using wsl.exe -d Ubuntu -- followed by the Linux command, with explicit path translation, working directory and exit-code handling. Keep Python and Ab3P in the same Linux execution path for the initial integration; native Windows live-resolver bridging would be a separate change. Record source revisions or source-tree hashes, compiler flags/version, executable hashes, WordData inputs/generated data hashes, library identity and notices. Document how path_Ab3P is resolved from another working directory.

## Acceptance criteria

- Real identify_abbr executes and upstream output comparison passes, or a concrete upstream discrepancy is retained and this task is not marked complete.
- Another build follows the recipe without source-path edits; installation identity covers executable, library and semantic resource files.
- Instructions explain running the Linux ABREX environment and exporting raw caches for Windows; no fictional native Windows binary is claimed.

## Verification

Upstream make test, dependency/resource-missing smoke, repeat build manifest comparison, repository fast gate. Use the commands and completion requirements in the Luna execution guide. Record actual commands, counts and results; never substitute fixture success for required real-data evidence.

## Scope and scientific boundary

No native Windows port, Docker installation, model download or benchmark tuning. System changes beyond the assigned build scope require the applicable environment authorization.

## Inputs and possible blockers

As of September 7, 2026, the user supplied C:/Users/mail/Documents/Projects/NCBITextLib; README.md, include/, lib/ and applications/ were inspected. Use this local source rather than requiring a fresh download. The sibling source is currently readable but outside the declared writable roots, so build from a copy in a task-owned writable location. Windows can invoke Linux commands through wsl.exe; run the ABREX/Ab3P live path inside Ubuntu with Linux paths, and retain Windows cache replay. A native Windows Python process does not load a Linux executable directly.

## Deliverables and completion note

Deliver the scoped implementation, typed configuration/example, meaningful tests, updated public documentation and any task-specific manifests/report described above. Keep large/generated source data, model weights and raw outputs outside tracked code; check in small permitted fixtures and reproducibility metadata.

Write `docs/tasks/completed/T018-build-and-verify-real-ab3p.md` only after acceptance checks, distinguishing completed engineering from scientific validation still pending. Include files changed, commands/results, artifact locations and fingerprints, open decisions, and the next ready task. Update this task's status and the task index without rewriting earlier historical completion notes.
