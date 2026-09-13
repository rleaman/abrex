# T058 repair and acceptance handoff — September 13, 2026

The user requested repair of the runtime/configuration issues and clear
instructions for Luna to revise T058. This repair does not itself declare
all T058 acceptance criteria satisfied or authorize T059/T060.

## Fixed and verified

- Corrected the existing T058 YAML to use the actual T021 installation manifest
  and pinned local PLOD checkpoint/hash; increased smoke timeouts to 120 seconds.
- Added `--require-all`: diagnostics are always saved, but incomplete method
  readiness gives a nonzero exit. Offline regression tests exercise both modes.
- Fixed the quality gate's virtualenv symlink handling. A POSIX regression
  verifies both explicit and discovered virtualenv interpreter selection.
- Added supplementary Unicode before definition spans in the smoke input.
- Preserved actual worker interpreter, Python version, source origin, PLOD
  package versions and resource identity in the new readiness report.
- Labeled the generic changed-input hash check's limited scope explicitly. It
  is not proof of prediction-cache replay or invalidation.
- Added the [runtime guide](baseline-runtimes.md), required from AGENTS.md and
  prominently linked from startup, Luna guidance, current work and task index.
  The original failure report remains unchanged; its completion claim now has
  an explicit correction notice.

## Evidence

[Repaired report](artifacts/T058-runtime-readiness-repaired.json): S&H, native
Ab3P, PLOD independent spans and PLOD pairing all available, complete 3/3,
no reported truncation. Counts: S&H 2 pairs, Ab3P 1 pair, PLOD 7 spans and
3 pairs. PLOD pairing conflict diagnostics remain visible; they are not worker
failures. Counts are operational evidence, not comparative accuracy.

The exact strict smoke command is in the runtime guide. This run used the
checked-in YAML with Linux orchestration, not the separate initial audit YAML.
Worker inputs/outputs are under `.artifacts/T058/verified-runtime/workers/`.
An additional read-only check verified identical worker input arrays, all 15
returned pair/span text slices and both optional methods' empty controls.

The documented WSL fast gate passed: source origin, Ruff format/lint, strict
mypy (179 source files), **373 tests**. This includes the existing actual Ab3P
cache round-trip regression, changed-text/config misses, and the new launcher,
strict-exit and Unicode regressions. `git diff --check` passed with only existing
Windows line-ending notices. Ten local guide/entrypoint Markdown links were
checked. No new dependencies, downloads, rebuilds or scientific policy changes.

## Luna's remaining closure work

1. Read the T058 specification, this handoff and the runtime guide. Preserve
   current user changes and original/frozen evidence.
2. Re-run the strict smoke into a new task-owned output location. Reconcile
   required input coverage, exact offsets, empty controls, separate PLOD spans
   and pairing, commands, origins/versions and hashes against actual artifacts.
3. Verify and document genuine cold/warm prediction-cache behavior and changed
   input/config invalidation using the existing cache interfaces and tests.
   Distinguish unit/contract evidence from a live replay. Do not cite the generic
   input fingerprint boolean as the cache acceptance test. Do not invent a new
   cache where a method has none; identify the actual caching layer being tested.
4. Check every remaining T058 criterion, implement only bounded gaps, run focused
   checks and the repository fast gate, and update the task status, completion
   note and task index consistently. Preserve original failed evidence with an
   explicit superseding report. Make no accuracy/complementarity claim.
5. Stop after T058. Do not revise T052/T057 frozen annotations or begin T059/T060.

Both methods worked without installation repairs. A later unavailable result
requires a fresh, exact prerequisite diagnostic using the documented paths.
