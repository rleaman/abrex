# T060 development comparison

The corrected four-way strict exact-pair comparison is materialized in
[`docs/artifacts/T060-development-comparison-split-v2.json`](../../docs/artifacts/T060-development-comparison-split-v2.json).
It joins all 20 frozen T057 passages to complete Schwartz–Hearst, Ab3P,
PLODv2-pairing and frozen-threshold split-question Jev prediction artifacts.
The unsuffixed comparison and packet preserve the superseded v1 Jev result.

The assisted T061 packet is
[`review-packet-split-v2.json`](review-packet-split-v2.json). It contains all
33 distinct predictions that did not exactly match an existing frozen T057
decision, deduplicated into 11 passages while retaining every
method contribution. These proposals are unreviewed; the strict comparison
does not treat them as new human judgments.

Launch the reviewer from the repository root:

```powershell
.\env313\Scripts\python.exe scripts/run_t060_reviewer.py
```

Open `http://127.0.0.1:8765`. Progress is saved beside the packet as
`review-packet-split-v2.annotations.json`; that sidecar is the T061 deliverable.

The first returned Linux archive completed Ab3P and PLOD pairing for all 20
documents with zero execution errors. It did not contain the independent PLOD
detector output needed to audit unpaired spans. The one-job follow-up archive
is `.artifacts/T060/abrex-t060-plod-spans-followup.zip`; it can reuse the
already installed server runtime. T060 remains open only for that span audit
and T061 human review. See the revival handoff for exact commands.

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
