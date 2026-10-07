# Milestone C independent second review

Status: **ready for a second human reviewer**

The source-only packet contains 36 passages selected exactly as approved: all
26 passages where the primary reviewer found a positive or diagnostic relation,
plus a seeded 10 of the 94 primary-negative passages. It contains no primary
answers, candidates, resolver outputs, confidence values, or model suggestions.
This review must be completed by a person other than the primary reviewer.
Estimated burden is 2.5–4 hours and may be split across sessions.

## Launch

From PowerShell in the Abrex project root, run:

```powershell
.\scripts\Review-Campaign-Milestone-C-Second.ps1
```

The launcher opens `http://127.0.0.1:8766/`. If that port is occupied, pass a
different one, for example `-Port 8767`.

For every displayed passage, the second reviewer should independently search
the entire passage, add every in-scope abbreviation definition using exact
source spans, and check **Searched this entire passage** even when no relation
exists. New relations default to **Abbreviation expansion**,
**Contiguous/shared**, and **Text alone**; change a field when the evidence
requires it. The **Shortcuts** button documents the keyboard controls:

- `Ctrl+Shift+C`: mark the displayed passage complete;
- `Ctrl+Enter`: add the relation currently entered;
- `Ctrl+Shift+Enter`: save and move to the next incomplete passage;
- `?`: open or close shortcut help outside an input field.

When all 36 passages are complete, select **Lock completed annotation**. The
server rejects an incomplete lock.

## Save, resume, and return

Drafts are saved atomically to
`evidence/campaign-2026-10/milestone-c/second-review-packet-blind-v1.annotations.json`.
Rerunning the launcher resumes the draft. The final lock is written beside it as
`second-review-packet-blind-v1.annotations.lock.json`.

After locking, the only return message needed is:

> second review complete

The campaign owner will validate the lock, construct a disagreement-only
adjudication interface with both reviewers' exact spans and provenance, import
the adjudicated gold, and continue the frozen comparison. The reviewer does not
need to copy files, run models, or reconcile disagreements manually.

## Verification

Microsoft Edge/Playwright exercised the actual 36-passage packet using
disposable state: complete listing, first/middle/last navigation, strict payload
allowlisting, defaults and shortcuts, save/reload, JSON export/import, and
incomplete-lock rejection. The authoritative empty state remained byte-identical.
Evidence is
`evidence/campaign-2026-10/milestone-c/second-review-browser-qa-v1.json`.
