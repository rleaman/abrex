# Coverage measurement boundary

ABREX retains a repository-wide 95% coverage floor for its domain, scientific,
configuration and application-service code. The threshold is not lowered.

Coverage omits only modules whose primary responsibility is an operating-system,
network, browser, filesystem, command-line or optional external-runtime boundary.
Those modules contain substantial defensive handling that cannot be exercised by
the fast offline unit suite without substituting the boundary itself. They remain
covered by focused contract tests, integration tests, captured-response tests and
recorded live smoke evidence.

The exact allowlist is in `pyproject.toml`. It covers:

- thin CLI dispatch;
- portable-job filesystem/process orchestration;
- historical-source, candidate-artifact and literature I/O adapters;
- bounded acquisition/pilot/reviewer orchestration and external worker entrypoints;
- Ab3P, BioADI infrastructure and the optional PLOD runtime boundary.

It does not omit the domain models, matching and metrics, candidate generation,
Jev response mapping/calibration/cache logic, CLP snapshot conversion, registry
composition, blind packet/lock contracts or experiment identity logic. New
scientific logic must not be added to an omitted module to evade the floor.
