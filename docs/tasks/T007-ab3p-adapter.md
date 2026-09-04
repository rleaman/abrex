# T007 - Ab3P Baseline Adapter

## Goal

Make the **original external Ab3P implementation** a reproducible resolver behind the common ABREX resolver contract, while supporting development and evaluation on machines where Ab3P cannot be installed or executed.

Ab3P execution is expected to occur primarily on a Linux system with an existing working installation. Windows development **must not require Ab3P, a C/C++ toolchain, WSL, administrator privileges, or any attempt to build/install Ab3P locally**.

A portable, provenance-preserving cache of Ab3P input/output pairs must allow previously executed benchmark documents to be resolved without invoking Ab3P again.

## Depends on

- T004 - canonical validation, serialization, manifests, and fingerprints;
- T005 - resolver interface and prediction artifact contract.

T006 evaluation behavior may be used in integration/acceptance tests, but T007 must not change matching or metric policy.

## Operational assumptions

The implementation must assume the following real deployment constraints:

1. **Windows workstation**
   - Ab3P is unavailable.
   - No compiler/toolchain should be assumed.
   - No WSL should be assumed.
   - No administrator access should be assumed.
   - Normal ABREX development, unit tests, cache-backed resolution, and benchmark analysis must work without Ab3P installed.

2. **Linux execution environment**
   - A working Ab3P executable already exists.
   - The executable path can be provided through YAML configuration.
   - Linux can be used to populate portable Ab3P caches for benchmark corpora.

3. **Portability requirement**
   - Cache artifacts produced on Linux must be consumable on Windows without path rewriting or dependence on the original temporary files.

Do not add SSH execution, remote-job submission, Docker, WSL invocation, or native Windows build support in T007. Those may be implemented later as separate infrastructure plugins if ever needed.

## Architectural intent

Keep Ab3P-specific scientific behavior separate from how Ab3P results are obtained.

Conceptually:

```text
Canonical Document
        |
        v
   Ab3P Resolver
        |
        +-----------------------------+
        |                             |
        v                             v
Cached execution                Live subprocess execution
(portable; no Ab3P)             (Linux; Ab3P executable)
        |                             |
        +-------------+---------------+
                      |
                      v
               Raw Ab3P result
                      |
                      v
               Ab3P output parser
                      |
                      v
       Canonical AbbreviationDefinition predictions
```

The exact class names are an implementation decision, but responsibilities must remain separable. In particular, parsing Ab3P output must not require a subprocess, and cache lookup must not be embedded inside scientific output parsing.

## Scope

Implement the following.

### 1. `ab3p` resolver plugin

Register an `ab3p` resolver through the existing resolver registry and YAML composition mechanisms.

The resolver must satisfy the same public resolver contract as other ABREX resolvers. Downstream evaluation code must not need to know whether predictions came from a live executable or a cache.

### 2. Configurable execution backend

Ab3P result acquisition must be configurable through a named backend/mode rather than inferred from the host operating system.

Support at least:

- `cache_only`
  - Never invokes an external executable.
  - Intended to be fully usable on Windows.
  - Returns a cached result only when an exact compatible cache entry exists.
  - A cache miss is an explicit structured execution error.

- `subprocess`
  - Invokes a configured Ab3P executable directly.
  - Intended for Linux systems with a working installation.
  - Does not require or use a shell.
  - May populate/update the cache when configured to do so.

Optionally support `cache_then_subprocess` if it can be implemented cleanly without coupling. In that mode, exact cache hits are used first and misses are executed live. Do not make this mode necessary for acceptance.

Do **not** implement automatic fallback from `cache_only` to any live execution mechanism.

### 3. External executable configuration

For live execution, support an explicitly configured executable path, for example:

```yaml
resolver:
  type: ab3p
  params:
    backend: subprocess
    executable: /opt/ab3p/Ab3P
    timeout_seconds: 60
    cache:
      path: artifacts/ab3p-cache
      write: true
```

The path may also refer to a command available through the process environment if the existing configuration framework supports this cleanly, but no platform-specific path should be hard-coded.

Use argument-vector subprocess invocation (`shell=False` semantics). Never construct shell commands containing document text.

### 4. Portable Ab3P cache

Implement a deterministic, inspectable, portable cache for results of real Ab3P executions.

The cache is not merely a performance optimization. It is an explicit reproducibility artifact enabling benchmark work on machines where Ab3P cannot run.

Each cached unit must preserve enough information to establish, at minimum:

- canonical document identity;
- canonical document/content fingerprint;
- the exact Ab3P input payload supplied to the executable, or a deterministic representation plus its fingerprint;
- raw Ab3P stdout/output used for parsing;
- stderr where relevant;
- exit status;
- timeout/failure status if applicable;
- Ab3P execution/provenance identity;
- adapter/cache schema version;
- relevant resolver configuration identity;
- creation metadata needed for auditability.

Where T004/T005 provide canonical dataset or prediction fingerprints, integrate with those identities rather than creating incompatible parallel concepts.

Cache keys must be **content/configuration based**, not dependent on absolute paths, temporary directories, hostnames, or operating-system-specific separators.

A cached result must never be accepted solely because its document ID matches. Changed document text, changed invocation-affecting configuration, incompatible cache schema, or incompatible Ab3P provenance must produce a cache miss or explicit incompatibility diagnostic.

### 5. Cache provenance and Ab3P identity

Capture Ab3P provenance as robustly as practical. Prefer stable machine-verifiable identity over assumptions.

When live execution is available, record where feasible:

- configured executable value;
- resolved executable path for diagnostics;
- SHA-256 of the executable binary, if practical and readable;
- version string if Ab3P exposes one reliably;
- invocation arguments/options;
- adapter implementation/schema version;
- execution platform metadata useful for debugging, without making platform data part of a cache key unless it affects semantics.

The portable cache must not require the same absolute executable path on the consuming machine.

If no official Ab3P version can be obtained programmatically, do not invent one. Record available evidence (for example binary digest and optional user-supplied installation label) explicitly.

### 6. Safe subprocess wrapper

Live execution mechanics belong in infrastructure, not domain code.

Implement:

- argument-vector invocation;
- timeout handling;
- stdout/stderr capture;
- exit-code capture;
- reliable cleanup of temporary files/directories;
- structured failures that identify the canonical document ID;
- no dependence on the current working directory unless Ab3P itself requires it and this is isolated/documented;
- no shell interpolation of document content.

If Ab3P requires file input, create the minimum required temporary artifacts and ensure cleanup in success and failure cases.

### 7. Ab3P input construction

Implement a deterministic conversion from a canonical ABREX document to the input representation supplied to Ab3P.

This transformation must be independently unit-testable and fingerprintable.

Preserve the exact input used for cache/provenance purposes so that a cached raw output can be traced back to the bytes/text Ab3P actually saw.

Do not silently normalize document text merely to make Ab3P happier. Any necessary transformation must be explicit, deterministic, documented, and reflected in coordinate mapping.

### 8. Ab3P output parser

Implement the parser independently of executable invocation.

It must accept captured raw Ab3P output and produce an intermediate parsed representation suitable for canonical span reconstruction.

Unit-test parsing using committed fixture outputs generated from representative real or faithfully captured Ab3P runs. Include malformed/truncated output cases.

The parser must not reach into the cache or subprocess infrastructure.

### 9. Canonical span reconstruction

Map Ab3P short-form/long-form predictions back to canonical `Document` spans and emit canonical `AbbreviationDefinition` predictions.

Requirements:

- preserve exact canonical half-open offsets;
- handle repeated surface strings without silently choosing an arbitrary occurrence;
- make reconstruction ambiguity explicit and testable;
- never fabricate offsets that cannot be justified from the document and Ab3P result;
- preserve raw/source diagnostic context needed to investigate mapping failures.

If the external Ab3P output does not contain sufficient offsets, reconstruction logic must be deterministic and isolated behind a testable component/strategy.

Do not change T006 matching semantics to accommodate mapping difficulties.

### 10. Cache population workflow

Provide a straightforward Linux workflow/CLI path to populate caches for a canonical benchmark artifact using the configured live Ab3P installation.

The precise command name may follow existing CLI conventions, but the workflow should allow a user to do conceptually:

```text
canonical benchmark artifact
    -> run Ab3P on Linux
    -> persist portable raw input/output/provenance cache
    -> emit normal canonical prediction artifact
```

It must be possible to copy the cache directory/artifact to a Windows checkout and resolve the same cached benchmark content with `cache_only` without invoking Ab3P.

Do not require the cache-population command to be run from any specific repository path.

### 11. Cache-backed prediction behavior

For a compatible cache hit, cache-backed resolution must feed the cached **raw Ab3P output through the same parser and canonical mapping path used for live execution**, unless there is a compelling documented reason not to.

Do not treat cached canonical predictions as the sole source of truth if that would allow parser/mapping changes to be bypassed silently.

It is acceptable to additionally cache parsed/canonical forms for diagnostics or performance, but raw Ab3P input/output must remain available as the reproducible baseline evidence.

### 12. Failure semantics

Clearly distinguish:

- Ab3P ran successfully and returned no abbreviation definitions;
- cache hit containing a successful zero-result Ab3P run;
- cache miss;
- cache entry incompatible with current input/configuration;
- Ab3P non-zero exit;
- Ab3P timeout;
- malformed/unparseable Ab3P output;
- canonical offset reconstruction failure/ambiguity.

None of these may be silently converted into an empty successful prediction set.

Use existing strict/permissive execution/error-policy mechanisms from T005 where appropriate rather than inventing a parallel global failure framework.

## Configuration

Configuration should use existing typed YAML and registry mechanisms. Avoid hard-coding execution policy.

Illustrative Linux configuration:

```yaml
resolver:
  type: ab3p
  params:
    backend: subprocess
    executable: /path/to/working/Ab3P
    timeout_seconds: 60
    cache:
      path: artifacts/ab3p-cache
      read: true
      write: true
    installation_label: nlm-linux-ab3p
```

Illustrative Windows/offline configuration:

```yaml
resolver:
  type: ab3p
  params:
    backend: cache_only
    cache:
      path: artifacts/ab3p-cache
      read: true
      write: false
```

These examples are illustrative rather than mandatory schema names. Follow the established ABREX configuration style and validation conventions.

## Engineering constraints

- Maximize cohesion and minimize coupling.
- Use existing registry hooks and typed YAML configuration.
- Subprocess mechanics belong in infrastructure, not domain.
- Cache mechanics must be separable from Ab3P scientific output parsing.
- Do not infer execution mode from Windows/Linux automatically.
- Do not require Ab3P for ordinary imports, unit tests, linting, typing, or package installation.
- Do not add Ab3P as a build-time dependency.
- Never shell-concatenate untrusted document text.
- Temporary files/directories must be cleaned reliably.
- Failures must identify document IDs and preserve diagnostic context.
- Offset reconstruction ambiguity must be explicit and testable.
- Cache artifacts must be deterministic and path-independent where identity/fingerprinting is concerned.
- Do not silently regenerate missing cache entries in `cache_only` mode.
- Do not introduce SSH, WSL, Docker, remote execution, or Windows compilation support.
- Do not reimplement the Ab3P algorithm in Python.
- Do not alter evaluation matching/metric semantics.

## Testing

### Unit tests - no Ab3P installation required

Ordinary unit/contract tests must run successfully on Windows without Ab3P.

Cover at least:

- deterministic Ab3P input construction;
- output parsing independently from execution;
- canonical offset reconstruction;
- repeated surface forms and ambiguous reconstruction;
- malformed output;
- cache key/fingerprint determinism;
- cache round-trip portability assumptions;
- cache hit;
- cache miss;
- cache incompatibility after document-content change;
- cache incompatibility after invocation-affecting config change;
- cached successful zero-result behavior;
- distinction between zero result and execution/cache failure;
- mocked subprocess success;
- mocked non-zero exit;
- mocked timeout;
- cleanup on success/failure;
- provenance serialization;
- YAML composition/registry injection.

Fixture raw outputs should be small and committed to the repository. Do not require an executable for parser tests.

### Integration tests - Ab3P required and explicitly marked

Provide clearly marked integration tests that run only when a real executable is intentionally configured.

Integration tests should verify:

1. live execution produces canonical predictions through the standard resolver interface;
2. the same live run can populate a cache;
3. the cached result can subsequently be consumed with live execution disabled;
4. live and cache-backed execution produce equivalent parsed/canonical predictions for the same input and adapter version;
5. cache/provenance artifacts contain sufficient execution identity for audit.

When no executable is configured, these integration tests must skip with a clear reason rather than fail.

Do not make the full ordinary repository quality gate depend on live Ab3P availability.

### Cross-platform acceptance

The implementation must be designed so that a cache produced by Linux integration tests can be copied to Windows and consumed by `cache_only` mode.

A committed tiny cache fixture may be used to exercise the portable-cache reader on every platform. If real Ab3P output is committed, document its source/provenance.

## Documentation

Document:

- that Ab3P itself is an optional external baseline executable rather than an ABREX dependency;
- that native Windows execution is not supported/required by T007;
- how to configure a working Linux Ab3P path;
- how to populate a benchmark cache on Linux;
- how to copy/use that cache in `cache_only` mode on Windows or another machine;
- cache compatibility/invalidation rules;
- how execution provenance is captured;
- the distinction between cache misses, execution failures, and legitimate zero predictions;
- how to run explicitly marked live integration tests.

## Acceptance criteria

T007 is complete when all of the following are true:

1. `ab3p` is a normal registry-backed resolver satisfying the T005 resolver contract.
2. On Linux, when a valid Ab3P executable path is configured, the resolver can invoke the real executable safely and emit canonical prediction artifacts.
3. A live Linux run can persist portable, inspectable Ab3P input/output/provenance cache entries.
4. On a machine with **no Ab3P installation**, `cache_only` mode can resolve previously cached benchmark documents and emit the same canonical predictions through the same resolver interface.
5. A cache miss or incompatibility is an explicit structured failure and can never masquerade as an empty Ab3P result.
6. Cached raw output passes through the same parser and canonical span reconstruction logic as live raw output.
7. Cache identity includes canonical input identity plus all invocation-affecting information required to prevent unsafe reuse.
8. Real executable provenance is captured as robustly as practical (preferably including binary digest when feasible), without inventing unavailable version information.
9. Unit/contract tests pass on Windows with no Ab3P executable, compiler, WSL, or administrator privileges.
10. Live integration tests are separately marked/configured and skip cleanly when Ab3P is unavailable.
11. No SSH/remote execution, Docker, WSL, Windows compilation, or Python reimplementation of Ab3P has been introduced.
12. Existing Ruff, mypy, pytest, and repository quality gates pass.

## Explicit non-goals

T007 does **not** include:

- installing or compiling Ab3P on Windows;
- installing WSL;
- requesting/automating administrator privileges;
- remote execution over SSH;
- scheduler integration for Linux servers;
- Docker/container packaging;
- rewriting/reimplementing Ab3P;
- changing scientific evaluation semantics;
- deciding whether Ab3P is the best baseline;
- corpus-specific benchmark policy beyond what is needed to exercise the adapter.

## Completion note requirements

When T007 is finished, the completion note must additionally report:

- which execution backends/modes were implemented;
- the cache identity/invalidation scheme;
- what Ab3P provenance is captured;
- whether a real Linux executable was exercised during development;
- whether a cache populated by live execution was successfully replayed without Ab3P;
- any known cases where canonical offset reconstruction is ambiguous;
- any remaining platform assumptions.
