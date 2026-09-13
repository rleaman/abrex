# T055 assisted audit reviewer

Status: Engineering delivered; browser acceptance is partial and remains pending
for the full selection/import/export matrix. No T056 adjudication or user
annotation was performed.

## Delivered

The existing local T052 reviewer was extended in place. It now provides:

- article title, source arm/section, bounded “Passage to review,” preserved
  paragraph whitespace, nearby source link, collapsed context, and separate
  collapsed technical details;
- persistent `Assisted review` disclosure and explicit `Supported`,
  `Unsupported`, and `Not sure` decisions with no default acceptance;
- pending/uncertain/changed filters, counts, case list, previous/next, save
  before navigation, durable save status, JSON/BioC backup controls, and
  packet-identity errors from the existing adapter;
- relation kind, evidence structure, required context, source-error and
  reconstructed-interpretation controls; additive review-model fields preserve
  these values without changing resolver/evaluator behavior;
- exact-position span selection plumbing, short/long-form assignment, ordered
  removable evidence fragments, repeated-text-safe offsets, and additive
  relations.

The immutable T052 evidence directory was not changed. The disposable browser
fixture used for QA was written outside the repository at
`C:\Users\mail\AppData\Local\Temp\abrex-t055-qa-packet.json`; its save sidecar
was `C:\Users\mail\AppData\Local\Temp\abrex-t055-qa-packet.annotations.json`.

## Launch and brief user guide

From the repository root:

```powershell
$env:PYTHONPATH = "src;env313/Lib/site-packages"
.\env313\Scripts\python.exe scripts/run_t052_reviewer.py <packet.json> --port 8765
```

Open `http://127.0.0.1:8765/`. Read the bounded passage, choose a decision for
each proposal, then separately mark the whole-passage search question. Select
text in the passage before using the short-form, long-form, or evidence-fragment
buttons. Save before navigating; the success banner names the durable revision.
Use JSON backup for restore/transport and Technical details only when offsets,
method identity, or diagnostics are needed.

## Browser record

Chrome loaded the disposable fixture at `http://127.0.0.1:8875/` with title
`ABREX literature review`. The accessibility tree showed the real article title,
passage, source link, proposal cards, exact decision labels, audit fields,
filters, navigation, backup/import controls, and no framework error overlay.
The inert `<img ...>` fixture text rendered as text rather than markup. Browser
actions completed: first proposal set to Unsupported, whole-passage state set
to Uncertain, relation kind set to Abbreviation expansion, source-error checked,
Save clicked, and the page reported `Saved revision 1 to disk.` Reload restored
the saved Unsupported status. The initial page had a transient stale-server
console error during development; after restarting with the final source the
page loaded cleanly and no new console error was observed.

The browser automation surface did not expose a reliable pointer-selection
primitive for this run, and did not expose a viewport override or a verified
file-upload/download assertion. Therefore the required full real-selection,
two-fragment, repeated-occurrence, import/export, supplementary-Unicode and
narrow-viewport acceptance matrix is explicitly pending; this note does not
call the interface user-ready or perform the human annotation step.

## Checks

- Focused dependency/reviewer regression: `13 passed in 0.97s`.
- `ruff check src tests`: all checks passed.
- `mypy`: no issues found in 173 source files.
- `pytest tests/unit tests/contract --basetemp .pytest-tmp/T055-fast -q`:
  `359 passed in 6.05s`.
- Canonical `scripts/quality_gate.py --python .\env313\Scripts\python.exe`:
  passed; `188 files already formatted`, Ruff passed, mypy passed, and
  `359 passed in 5.82s`.
- `git diff --check`: passed; only the existing LF/CRLF normalization warnings
  were emitted for modified Python files.
- `git diff --quiet -- evidence/T052`: passed; frozen T052 bundle remains
  byte-identical in the working tree.

Next dependency: T056 human T052 adjudication, performed by the user; no work
from that task was started here.
