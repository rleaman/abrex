# T061 minimal assisted review (complete)

The final review packet contained exactly one scientific judgment that was not
already settled by completed T061 work, frozen T057 evidence, or the frozen
exact-boundary policy:

> Does this passage define `SR-BI` as `scavenger receptor class B type 1`?

The complete 33-proposal source packet remains at
[`../T060/review-packet-split-v2.json`](../T060/review-packet-split-v2.json).
The seven passages already reviewed by the user remain unchanged in its
`.annotations.json` sidecar. [`triage.json`](triage.json) accounts for every
source proposal: 15 already reviewed, 17 resolved from frozen evidence or
policy, and one retained for user judgment. Machine-derived resolutions are
not relabeled as new human annotations.

Launch the one-question review from the repository root:

```powershell
.\scripts\Review-T061.ps1
```

The exact spans and structural fields are mechanically prefilled. The earlier
whole-passage search is reused. Choose only **Supported** or **Unsupported**,
then click **Save and next incomplete**. Check completion with:

```powershell
.\scripts\Review-T061.ps1 -Check
```

The user marked the full pair **Supported**. The working file is
`review-packet-minimal.annotations.json`; `Review-T061.ps1 -Check` reports 1/1
complete. The prefill's
history and notes explicitly identify the fields that were carried forward;
the support choice remains the user's judgment.
