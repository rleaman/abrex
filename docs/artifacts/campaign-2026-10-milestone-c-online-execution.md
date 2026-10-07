# Milestone C online prediction execution

Status: **complete within authorized caps; scoring withheld**

The scientific lead authorized the post-lock TypeSafe and Azure OpenAI runs on
October 7, 2026. Both executed only after the primary annotation lock and used
the frozen prediction-only dataset. Neither run accessed local gold.

## TypeSafe Jev

The shared TypeSafe limit covered the single complete-CLP judgment plus the 64
candidate-judge batches. All 65 requests completed with no retry or failure and
returned `jev-1.13.0`.

- Actual input: 548,385 tokens against the 724,000-token cap.
- Estimated cost: $0.02303217 against the $0.05 cap, using TypeSafe's current
  published $0.042 per million input-token rate; output is unmetered.
- Complete CLP: one applicable source-declared ABBR section,
  `NEEDS_PARSER_EXTENSION`, zero exact pairs.
- Jev candidate judge: 45 predictions across 120 document records, zero resolver
  failures.

The other structural and representative passages remain non-applicable to the
complete CLP ABBR-section contract; they are not counted as empty CLP
predictions.

## Azure OpenAI GPT-6 Luna

The frozen quote-grounded iteration-2 prompt completed all 120 requests with no
retry or request failure.

- Actual usage: 115,653 input and 9,807 output tokens.
- Actual cost: $0.0164688 against the $0.10 hard cap.
- Grounded predictions: 68 across 120 document records.
- Exact-grounding diagnostics: five dropped proposals. One used the one-letter
  short form `D`, which also occurs inside its long form; four supplied evidence
  quotes that occur more than once in the passage. No fuzzy or gold-assisted
  repair was applied.

## Evidence boundary

`evidence/campaign-2026-10/milestone-c/online-execution-receipt-v1.json` binds
the provider caches, Luna attempt ledger, prediction files, usage, cost, models,
request counts, and SHA-256 hashes. Confirmatory scoring remains withheld until
the independent second-review lock and disagreement adjudication establish the
final gold. The Linux Ab3P/PLODv2 return is also still pending.
