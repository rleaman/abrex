# Historical planning archive

The files below were retired as execution guidance on October 5, 2026. They
explain prior plans, instructions and status; they are not current assignments.
Use [current work](../CURRENT_WORK.md), [AGENTS.md](../../AGENTS.md), and the
[active campaign](../experiment-campaign-2026-10.md) for execution.

| Historical text | Current replacement |
| --- | --- |
| [Bootstrap handoff](planning/START_HERE_FOR_CODEX.md) | [Start here](../../START_HERE_FOR_CODEX.md) |
| [Work checkpoints through T068](planning/current-work-through-t068.md) | [Current work](../CURRENT_WORK.md) |
| [Old task index](planning/task-index-through-t068.md) | [Task records index](../tasks/README.md) |
| [Project completion plan](planning/project-completion-plan.md) | Active campaign |
| [Post-T052 plan](planning/post-t052-next-steps.md) | Active campaign |
| [Luna execution guide](planning/LUNA_EXECUTION_GUIDE.md) | AGENTS.md and active campaign |
| [T050-T052 recovery acceptance](planning/recovery-acceptance.md) | Current milestone acceptance |
| [October 2 revival handoff](planning/revival-handoff-2026-10-02.md) | Current work and applicable runtime guides |
| [T058 repair handoff](planning/t058-repair-handoff.md) | [Baseline runtime guide](../baseline-runtimes.md) |

Old entry-point paths remain as concise navigation or retirement notices, so
existing links continue to work. Archived planning text has a retirement banner
and rebased Markdown links. Git history preserves its exact prior representation.

## Evidence and contracts are separate

Frozen evidence bundles, annotations, result artifacts and completion notes stay
at their stable paths. Dated audits retain their observation dates; their old
recommendations and runtime availability statements are not current instructions.
Numbered task specifications remain available for historical acceptance criteria
and scientific decisions, including deferred original-backlog work. The active
assignment determines whether any such work is now in scope.

Scientific contracts, annotation policies, architecture, settled resource
decisions, and the baseline/Linux-server runtime guides remain active documents.
Do not infer deprecation merely from age or from a reference to an old task ID.
Do not delete scientific provenance as part of instruction cleanup.

## Search behavior

The root `.rgignore` excludes this archive's planning subdirectory and historical
numbered task specifications from default recursive ripgrep searches. It does
not hide results, evidence bundles, completion notes or active contracts.
To deliberately inspect historical planning or task specifications:

```powershell
rg --no-ignore "one task at a time" docs/archive/planning
rg --no-ignore "exact pair" docs/tasks
```

Other search tools, including `git grep`, can still find archived text. Explicit
file reads also remain possible. Directory names, retirement notices and the
standing instruction-precedence rule provide the authority boundary; search
exclusions only reduce noise.
