# T064 prediction-blind review mode

Status: Complete — implementation and real-browser QA verified October 2,
2026.

Blind review has a separate `abrex-blind-review-packet-v1` source-only schema,
HTML application, browser state, API payload, and lock export. Assisted packets
are rejected in blind mode; predictions, method identities, confidence,
proposed spans, and answer data are absent rather than hidden. The workflow
supports exact selection, relation add/edit/remove, multi-fragment evidence,
uncertainty, explicit whole-passage completion, true zero-relation cases,
save/resume, deterministic JSON backup/import, keyboard access, progress, and
immutable lock/export with an exposure flag.

Automated API/contract tests and a real Microsoft Edge Playwright run covered
payload isolation, relation creation from scratch, Unicode and repeated text,
save/reload, zero-relation completion, JSON export/import, server-enforced
locking, locked export, and a 390×844 viewport. The recorded QA artifact is
[T064-browser-qa.json](../../artifacts/T064-browser-qa.json). No unseen fresh
evaluation material was used for UI testing or annotation.

The final repository gate passed with 408 tests, one optional skip, Ruff,
strict mypy, and 95.18% coverage. T065 still requires the explicit T063
scientific decision before acquisition.
