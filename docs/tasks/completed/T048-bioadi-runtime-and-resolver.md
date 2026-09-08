# T048 completion note: BioADI runtime and resolver integration

## Follow-up: Java blocker resolved September 7, 2026

User-local Temurin Java 8 is installed in WSL. Explicit execution of
`aiiaadi.util.Executor` from the acquired JAR produced real BioADI predictions
on a five-record CPU smoke. The manifest's `SentParDetector` entry point is
not the extraction command. See [runtime instructions and evidence](../../bioadi-runtime.md).
The adapter integration and bounded T022 comparison below complete the
remaining implementation scope. The earlier negative current-environment
assessment is retained as history.

Status: Complete for the bounded integration and feasibility outcome. The
comparison deliberately reports execution failures separately from scored
predictions.

## Delivered

- Acquired the exact supplied BioADI JAR and preserved it outside Git under
  `.artifacts/T048/`.
- Inspected the JAR manifest, package/resource layout and embedded dependency
  metadata. The artifact is 5,237,679 bytes with SHA-256
  `62e92f3debc0b792c6ee0678a88c30102dec349c7f337befa427de232014975a`; it
  contains 2,975 ZIP entries and names `spiaotools.SentParDetector` as its
  main class. BioADI-related classes and embedded `Model`/stop-word resources
  are present, but no BioADI Maven POM is embedded.
- Ran the bounded command-line smoke in WSL. It failed before input
  processing because Java is not installed; the Windows environment likewise
  lacks `java` and `jar`.
- Re-ran the smoke with the explicit user-local Temurin JDK 8 path and verified
  real extraction, Unicode input, repeated forms and empty output. The JAR is
  invoked through `aiiaadi.util.Executor`; the manifest's main class is not
  the extraction entry point.
- Added a typed registry-backed resolver and infrastructure boundary with
  explicit JAR digest, Java path, resource bounds, cache identity and
  structured execution errors. The adapter maps only exact occurrence counts;
  it never invents offsets.
- Added offline parser, mapping, identity, subprocess and timeout tests in
  `tests/unit/test_bioadi.py`, plus the standard benchmark configuration at
  `configs/benchmarks/T048-bioadi-t022.yaml`.

## Verification and evidence

The captured runtime result is in
[bioadi-runtime-smoke.json](../../artifacts/bioadi-runtime-smoke.json). The
bounded comparison report is in
[T048-bioadi-resolver-report.json](../../artifacts/T048-bioadi-resolver-report.json),
and its ignored prediction artifact is
`.artifacts/T048/bioadi-t022-predictions.jsonl`.

The standard resolver path processed all 64 T022 records: 13 records produced
9 canonical predictions and 51 records produced explicit cardinality-mapping
failures. On the 13 successful records only, exact-pair matching was TP=8,
FP=1, FN=9, precision=0.8888888889, recall=0.4705882353 and F1=0.6153846154.
The standard evaluator refused to score the full set because execution
failures are not legitimate empty prediction sets; the full-subset treatment
is intentionally left as a scientific decision.

## Feasibility decision and limitations

BioADI is operationally verified for a bounded local pilot and integrated as an
optional resolver. Its output has no offsets, so exact occurrence cardinality
is the safe mapping boundary. Repeated short forms or long forms that do not
reconcile cause explicit document failures. Scores remain uncalibrated scores,
not confidence. The T022 corpus is not treated as an independent BioADI test,
and no publication or license equivalence claim is made.

## Next ready tasks

T030 and T047 are complete as bounded/provisional deliverables. T023/T024
remain gated by the unresolved live PLOD runtime path; T031 remains gated by
T024. Before using BioADI in T031, decide how resolver abstentions are scored,
whether `ordered_occurrence` is acceptable for the target corpus, and whether
the supplied artifact's license/publication provenance is sufficient.
