# T048 Verify BioADI software and integrate a viable resolver

Status: Complete for bounded runtime verification, typed integration and the
T022 resolver artifact. The evaluator treatment of the 51 explicit mapping
failures remains an open scientific decision; see the [completion note](completed/T048-bioadi-runtime-and-resolver.md).
Assigned implementer: GPT-5.6 Luna. Milestone: B/C. Added September 7, 2026;
run after the real baseline path, then include usable results in T031/T040 comparisons.

## Outcome

Determine whether the available BioADI Java artifact can serve as a reproducible resolver and integrate it if viable. The existing BioADI corpus adapter does not execute this software.

## Dependencies and reading

[T017](T017-reproducible-development-environments.md), [T019](T019-audit-and-repair-corpus-semantics.md), [T022](T022-real-baseline-smoke-benchmarks.md).

Read AGENTS.md, START_HERE_FOR_CODEX.md, [Luna execution guide](LUNA_EXECUTION_GUIDE.md), [resource catalog](../resource-catalog.md), docs/resolvers.md and CSV row 9. Inspect the BioADI publication and artifact metadata to establish provenance and API rather than assuming a standalone main class.

## Implementation steps

1. Acquire and hash the exact [supplied artifact](https://clojars.org/repo/edu/sinica/bioagent/bioadi/0.1.0/bioadi-0.1.0.jar). A September 7 HEAD request returned HTTP 200, Content-Length 5237679 and application/x-java-archive. The planning check did not download or execute it.
2. Inspect the manifest, package metadata, classes, model files and dependency declarations. Establish whether this is original BioADI, a repackaging or a wrapper. Record Java versions, resource lookup, entry point/API and notices. Do not assume a JAR is self-contained or supports java -jar.
3. Run a bounded CPU smoke with explicit inputs, timeouts and retained stdout/stderr. Verify output meaning, offset units or mapping limitations, Unicode, repeated forms and empty outputs. Never manufacture offsets to force compatibility.
4. If viable, implement a typed registry-backed bioadi resolver with process execution behind infrastructure, explicit Java/JAR/model identities and cache invalidation. Reuse canonical prediction/error contracts and retain live-derived fixtures separately from synthetic tests.
5. Compare real predictions on the T022 subset. Use T031 analysis for unique correct pairs, failures and runtime when available. Record NatLAb, AbbrAlignHMM, ALICE and other systems as follow-up candidates; implementing them is outside this task.

## Acceptance criteria

- Reproducible acquisition/provenance and runtime evidence distinguishes a reachable artifact from usable software and verified predictions.
- If usable, the resolver runs on a real audited corpus through the standard experiment path, with valid canonical spans, explicit failures and external identities.
- If unusable, record concrete incompatibilities or missing dependencies and attempted supported remedies. This completes only the feasibility outcome, not an implemented-resolver claim. A network timeout alone leaves access pending.
- Training/evaluation overlap and wrapper differences are reported; the BioADI corpus is not automatically an independent test of the BioADI model.

## Verification

Parser/process/mapping and cache-identity tests, marked skippable live Java smoke, real T022 comparison when viable, repository fast gate. Ordinary tests remain offline and cover runtime failures.

## Scope and scientific boundary

No Java dependency in the core import path, BioADI retraining, algorithm rewrite or blanket implementation of CSV systems. Artifact availability alone does not establish author provenance, license or scientific equivalence.

## Inputs and possible blockers

Java, transitive libraries, model resources and the actual API remain unverified. Preserve an explicit negative feasibility result if supported operation cannot be established; this task does not block the existing Ab3P/PLOD baseline sequence.

## Deliverables and completion note

Deliver a runtime assessment, artifact manifests, tests and, when viable, the resolver/configuration and real comparison. Record the precise feasibility and adapter status in docs/tasks/completed/T048-bioadi-runtime-and-resolver.md. Keep third-party binaries/models untracked.
