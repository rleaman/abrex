# Finish the T057 review

Status: completed September 13, 2026. Retained as the reproducible operating
guide for checking or revisiting this review; no further user action is needed
for T057.

You only need to review **20 passages**, not the full 60-case T052 packet.
Your work already exists and will be loaded automatically.

## Open the right review

From the project folder, run:

```powershell
.\scripts\Review-T057.ps1
```

The page opens automatically. Keep the PowerShell window open while reviewing.
To pause, save the current passage and press **Ctrl+C** in PowerShell. Run the
same command later to resume.

The only working annotation file is:

```text
evidence/T052/review-packet-v2.annotations.json
```

The page shows this path. **Save passage** writes directly to it. The JSON
backup button downloads a second copy for recovery; it is not a different
annotation task. Do not edit the frozen
`review-packet-v2.annotations.final.json` baseline.

## What to do in each passage

The default **Needs attention** filter shows only unfinished passages.

1. Read the complete boxed passage and look for missing definitions. Add any
   supported relation that is absent.
2. Mark every relation **Supported** or **Unsupported**. Use **Not sure** only
   when you genuinely cannot decide; it deliberately leaves the review open.
3. For every supported relation, choose **Review relation details** and set:
   - **Relation kind:** `Abbreviation expansion` for the narrow extraction
     target, or `Other naming or code relation` when it is worth preserving but
     outside that target.
   - **Evidence structure:** `Contiguous/shared` when the displayed long-form
     span is the complete source evidence, or `Discontinuous` when additional
     non-adjacent words are required. For discontinuous evidence, select and
     add each additional exact fragment. The long-form and evidence fragments
     must not overlap or duplicate one another.
   - **Required context:** `Text alone`, `Document structure`, or `Image`.
4. After searching the whole passage, choose **Searched**.
5. Click **Save passage**. Use **Save and next incomplete** to move through the
   remaining work.

Orange relation cards state exactly which fields remain. A green check beside
a passage means its support decisions, policy fields, evidence requirements and
whole-passage search are complete.

## How to know you are done

The banner at the top-right must say:

```text
Ready: all 20 required passages are complete.
```

For an independent check after closing the reviewer, run:

```powershell
.\scripts\Review-T057.ps1 -Check
```

It exits successfully only when all 20 passages satisfy the same rules used by
the page. If work remains, it gives a short passage list rather than dumping
every annotation field.

## What does not need to be resolved

You do not need to invent a universal theory separating abbreviations, labels,
symbols and derived names. Make the relation-level choice supported by this
passage. Genuine uncertainty can remain, but it means T057 is not ready to
freeze ordinary precision/recall denominators; tell Codex which cases remain
uncertain when you return the file.

Figure visuals, including arrows and colors, remain out of scope. Preserve a
textual proposal as unsupported or as an outside-target relation where
appropriate; do not annotate image geometry.
