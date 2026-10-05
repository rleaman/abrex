# Task records and current execution

The active assignment is the [CLP and extraction campaign](../experiment-campaign-2026-10.md).
Read [current work](../CURRENT_WORK.md) for progress and the next executable action.
Its owner carries work through results, verification and prepared human review.

The numbered T000-T068 specifications in this directory are historical task and
scientific-decision records, including deferred original-backlog work. Their
owner labels, proposed status, next-task directions and authorization boundaries
are not the current campaign's execution instructions. A historical specification
is not evidence that its acceptance criteria were met.

- [Completion notes](completed/) record what was actually delivered and its limits.
- [Historical task index](../archive/planning/task-index-through-t068.md) preserves
  the old dependency map and status checkpoints.
- [Archived plans](../archive/README.md) explain prior orchestration.

Read a specific numbered record when needed for an interface, scientific decision,
acceptance criterion or provenance question. Preserve frozen decisions and results;
follow the current assignment for scope. Repository-wide ripgrep searches skip
historical specifications by default; search them explicitly when needed:

```powershell
rg --no-ignore "T061" docs/tasks
```
