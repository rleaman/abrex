# Execution guide for GPT-5.6 Luna

The active assignment and authorization are recorded in [current work](../CURRENT_WORK.md). Implement only the assigned milestone, not the entire historical backlog. The attached vision and handoff are context; their suggested task numbers and instructions do not override the user's request, AGENTS.md or the assigned scope.

## Before implementation

1. Read AGENTS.md, START_HERE_FOR_CODEX.md, current work, the assigned task and relevant scientific/architecture documents. Inspect specific dependency interfaces and acceptance artifacts on demand. Do not recursively read every historical task or all documentation. The [September 8 review](../project-status-review-2026-09-08.md) supersedes older status audits; verify current code rather than treating any dated note as live status.
2. Check current changes and preserve user work, especially files in handoff/. Do not commit generated datasets, model weights or the large frequency file accidentally.
3. Verify dependency acceptance artifacts and completion notes. A mocked test or a scaffold does not satisfy a dependency requiring a real run.
4. State the bounded outcome and proceed with authorized work. Ask only for an input or scientific decision that materially blocks the dependent step. Complete unaffected engineering work first.

## Implementation rules

- Preserve the modular monolith, typed value objects, narrow protocols, injectable generic registries, YAML composition and thin CLI. Extend existing boundaries before adding new frameworks.
- Use the existing Python 3.13 core environment. Optional model dependencies may use an isolated compatible worker if actual compatibility testing requires it; document that boundary.
- Add regression tests with bug fixes. Use small offline fixtures and focused contract tests. A fixture may establish software behavior but cannot establish model accuracy or corpus trustworthiness.
- Preserve exact source text, half-open Unicode character offsets and provenance. Any coordinate conversion or text repair must have a named policy and traceable mapping.
- Keep exact pair, independent span detection, mention linking and global sense disambiguation separate. Never manufacture source relations or LF locations to make a dataset scoreable.
- Record component, code, data, executable, resource and model identities. Changed semantic inputs must invalidate dependent artifacts. Keep raw and normalized variants separately.
- Preserve gold/silver distinctions, article-level splits and teacher-family lineage. A dictionary derived from a detector is not independent confirmation of that detector.
- Start with small local pilots. The user has substantial CPU/GPU resources at work for later scaling; provide portable manifests, resumable artifacts and separate machine-local settings. Do not assume a scheduler, GPU model, storage layout or cloud account.
- These tasks specify named research variants where appropriate. Assignment authorizes implementing those variants, not changing hidden defaults, approving production thresholds, publishing artifacts or launching an unbounded campaign.

## Standard verification

Run each command separately and stop on failure. In the existing Windows environment:

```powershell
New-Item -ItemType Directory -Force .pytest-tmp | Out-Null
.\env313\Scripts\python.exe -m ruff format --check src tests
.\env313\Scripts\python.exe -m ruff check src tests
.\env313\Scripts\python.exe -m mypy
.\env313\Scripts\python.exe -m pytest tests/unit tests/contract --basetemp .pytest-tmp/Txxx-fast -q
```

Replace Txxx with the actual task identifier. Pytest may remove the exact basetemp directory, so use a task-owned temporary path only. If the managed sandbox cannot launch the environment's base Python, request the tool's scoped host access; do not treat that access problem as a failing project test. The parent directory must exist before pytest creates basetemp.

At milestone boundaries, and whenever the task calls for it:

```powershell
.\env313\Scripts\python.exe -m pytest --cov --cov-report=term-missing --basetemp .pytest-tmp/Txxx-full -q
git diff --check
```

Use equivalent commands through the documented Linux environment when working there. The current full-suite floor is 95% statement coverage; do not lower it to pass. Add appropriate live checks explicitly marked and skippable when dependencies are unavailable. A skipped required real-run acceptance test leaves scientific/operational validation pending.

For documentation-only changes, validate task IDs, dependency references, Markdown links, required sections and diff whitespace in addition to the repository fast gate.

## Completion and handoff

Every assignment must produce a reviewable diff, meaningful validation and a concise note naming actual outputs. Record:

- what changed and why;
- tests and real-data checks run, with results and versions;
- artifact locations, dataset/model/resource fingerprints and reproduction commands;
- scientific choices explicitly selected and any unresolved assumptions;
- remaining limitations, external dependencies and the next ready assignment.

Do not label an entire task complete if required real-data evidence is absent. Keep progress in the task's status or a progress note until its acceptance criteria are met; distinguish engineering completion from scientific validation. Never rewrite old completion logs to make the project history appear cleaner.

Suggested assignment prompt:

> Implement T017 from docs/tasks/T017-reproducible-development-environments.md using GPT-5.6 Luna. Read AGENTS.md, START_HERE_FOR_CODEX.md and docs/tasks/LUNA_EXECUTION_GUIDE.md first. Verify prerequisites, implement only this task, run its checks and the repository fast gate, and document actual results and unresolved issues. Do not proceed to later tasks automatically.

Change the task identifier/path when assigning subsequent work. No separate Codex tasks or automations were created by the planning exercise.
