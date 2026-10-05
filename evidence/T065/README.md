# T065 fresh prediction-blind packet

T063 was approved without revision. T065 then selected eight new linked
PMID/PMCID article groups using seed `20261002`, prior-evidence identity
exclusions, exact CC BY license evidence, and source structure only. No
resolver, model, candidate generator, abbreviation-token heuristic, or
prediction output was run against these sources.

The delivered packet has 32 cases:

- 12 PMC prose passages;
- 12 PubMed abstract passages;
- 8 table/list sections;
- exactly 4 cases from each of 8 article groups.

The immutable packet is `review-packet-blind-v1.json`. The adjacent
`review-packet-blind-v1.annotations.json` is the initially empty draft state.
The complete acquisition/exclusion/source/hash record is
`source-manifest-v1.json`; accepted raw XML is retained under the ignored
`.artifacts/T065/fresh-sample-v1/raw` directory.

## Start T066

From PowerShell in the project root:

```powershell
.\scripts\Review-T066.ps1
```

Review only the bounded **Passage to review**. The article title and any
surrounding context are non-annotatable. Add every in-scope abbreviation
definition in the passage using exact short-form and long-form spans. Confirm
the whole-passage search even when no relation is present. Save drafts as often
as useful.

After all 32 cases are complete, use **Lock completed annotation**. The lock is
the prediction-blind boundary required before T067 may run the evaluated
methods. The only files needed back are the annotation state and its generated
`.lock.json` file; when reviewing in this checkout they are already saved in
this directory.
