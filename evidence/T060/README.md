# T060 development comparison

The corrected four-way strict exact-pair comparison is materialized in
[`docs/artifacts/T060-development-comparison-split-v2.json`](../../docs/artifacts/T060-development-comparison-split-v2.json).
It joins all 20 frozen T057 passages to complete Schwartz–Hearst, Ab3P,
PLODv2-pairing and frozen-threshold split-question Jev prediction artifacts.
The unsuffixed comparison and packet preserve the superseded v1 Jev result.

The exhaustive T061 source packet is
[`review-packet-split-v2.json`](review-packet-split-v2.json). It contains all
33 distinct predictions that did not exactly match an existing frozen T057
decision, deduplicated into 11 passages while retaining every method
contribution. Seven passages and 15 proposals have already been reviewed. A
subsequent evidence-preserving triage removed repeated work: 17 further
proposals are resolved by the frozen T057 decisions/search or exact-boundary
policy, leaving one scientific judgment in the
[`../T061` minimal packet](../T061/README.md).

Launch the reviewer from the repository root:

```powershell
.\scripts\Review-T061.ps1
```

Open `http://127.0.0.1:8765`. Progress is saved in
`../T061/review-packet-minimal.annotations.json`. The original
`review-packet-split-v2.annotations.json` is preserved as part of the combined
T061 evidence and must not be overwritten.

The first returned Linux archive completed Ab3P and PLOD pairing for all 20
documents with zero execution errors. The returned one-job follow-up also
completed independent PLOD detection for all 20 documents in 89.15 seconds
with no execution errors. Its result is imported under
`.artifacts/T060/imported-linux-results/t060-plodv2-spans-linux`. The completed
audit records 275 independent endpoints (239 short-form and 36 long-form), all
72 endpoints used by PLOD pairing, and 203 detector-only endpoints. Independent
spans are not definition-pair judgments and do not create additional human
annotation work. T060 and T061 are complete; the T062 readout is available in
[`../T062`](../T062/README.md). Follow the
[T060/T061 runbook](../../docs/t060-t061-runbook.md) for exact commands.

The imported return archive is retained at
`.artifacts/T060/returned-results/abrex-results-71ed8dc6d27ab7b9002fbdd98130a9b3184c3c5884e66113ed407adfa399e5b8.zip`
with SHA-256
`66eae7326ab3730b5e37328e4f169a42e8261d6c3fe0888a9e31a8d81a3b38a9`.

[`manifest-split-v2.json`](manifest-split-v2.json) hashes the frozen inputs and
both generated
outputs. Rebuild them with:

```powershell
.\env313\Scripts\python.exe scripts/build_t060_development.py
```
