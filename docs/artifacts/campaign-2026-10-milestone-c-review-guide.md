# Milestone C prediction-blind review

Status: **ready for primary scientific annotation**

The frozen packet contains 120 source passages from 72 disjoint article groups:

- 48 PMC prose passages and 48 linked PubMed abstracts from the representative
  exact-CC-BY frame;
- 24 separately labeled source-structural challenge passages;
- no gold annotations, candidates, resolver outputs, confidence values, or model
  suggestions.

The remaining primary scientific task is to find every in-scope abbreviation
definition in each passage using exact source spans. The approved burden estimate
is 8–12 hours. Work can be split across sessions.

## Launch

From PowerShell in the project root, run:

```powershell
.\scripts\Review-Campaign-Milestone-C.ps1
```

The tested launcher opens `http://127.0.0.1:8765/`. It reports packet
`blind-d25c221acdb3a40f0e22` and 120 passages. If that port is occupied, use
`-Port 8766` or another local port.

For each passage:

1. Search the complete displayed passage.
2. Add every in-scope abbreviation relation by selecting the exact long-form
   and short-form occurrences. Repeated strings are distinguished by position.
3. Confirm the relation-kind, evidence-structure, and required-context fields.
   New relations default to **Abbreviation expansion**, **Contiguous/shared**, and
   **Text alone**; change any field to **Uncertain** or another value when needed.
4. If no relation exists, still check **Searched this entire passage**.
5. Use **Save draft** or **Save and next**. Only the displayed passage is
   annotatable; titles and surrounding context are not.

The **Shortcuts** button in the header provides an unobtrusive reminder. The
main shortcuts are:

- `Ctrl+Shift+C`: mark the displayed passage complete;
- `Ctrl+Enter`: add the relation currently entered in the editor;
- `Ctrl+Shift+Enter`: save the displayed passage and move to the next passage
  needing attention;
- `?`: open or close shortcut help when focus is outside an input field.

When every passage is complete, choose **Lock completed annotation**. An
incomplete lock is rejected by the server.

## Save, resume, and return

Drafts are written atomically to:

`evidence/campaign-2026-10/milestone-c/review-packet-blind-v1.annotations.json`

Rerun the same launcher to resume at the saved passage. **JSON backup** creates
an optional portable copy; **Import JSON** validates packet identity and revision
history before saving. The final lock is written beside the draft as
`review-packet-blind-v1.annotations.lock.json`.

After locking, reply only:

> review complete

The campaign owner will locate and validate both files, construct a separate
prediction-blind second-review subset (all positive/uncertain/diagnostic cases
plus a seeded 10% of negatives), and continue the authorized work. No copying,
renaming, candidate generation, model execution, or result bookkeeping is
required from the reviewer.

## Verification already completed

The actual packet passed Microsoft Edge/Playwright checks for all 120 list
entries, first/middle/last navigation, strict source-payload allowlisting,
the relation defaults and keyboard shortcuts, disposable save/reload, JSON
backup/import, and rejection of an incomplete lock. The live annotation state
remained byte-identical. Evidence is
`evidence/campaign-2026-10/milestone-c/actual-packet-browser-qa-v1.json`.
