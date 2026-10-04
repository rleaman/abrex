# T059 bounded language-model adapter

Status: Complete — engineering and bounded development evidence verified
October 2, 2026.

The registry-backed `jev_candidate_judge` resolver uses pinned
`typesafe-sdk==0.7.2`, model `jev-1.13.0`, and policy
`abrex-candidate-choice-v1`. Following TypeSafe's selection/judgment contract,
deterministic code supplies exact-span candidates and Jev chooses forward,
reverse, or not-definition; Jev does not generate source text or offsets.

Requests are bounded to 48,000 serialized characters and 64 candidates, with
30-second timeouts, three retries, concurrency eight, 500 requests, and ten
million input tokens per experiment. Cache identity includes the pinned model,
policy, state, questions, and candidates. Neutral provenance records choices,
probabilities, confidence, usage, request IDs, latency, attempts, and cache
status without credentials.

The live 20-passage development run completed with no request failures. It
used 225,965 input tokens over 26 requests, with mean reported request latency
0.218 seconds and estimated input cost $0.00949 at the supplied rate. The
frozen 0.60 threshold produced 29 TP, 24 FP and 30 FN (strict pair F1 0.5179).
Candidate coverage was 47/59 (79.66%). These are assisted development results,
not untouched evaluation evidence. The complete machine-readable record is
[T059-jev-development.json](../../artifacts/T059-jev-development.json).

## October 4 correction

The v1 question above conflated two independently useful judgments: whether the
exact pair is a definition and, if so, its orientation. It remains available
for historical reproduction only. Resolver v2 uses policy
`abrex-candidate-split-v2`: one Noul for definition validity and one speculative
Choice for orientation, evaluated together over the same state.

The corrected run used 347,692 input tokens over 38 requests, cost about
$0.0146 at the supplied rate, and had no failures. Joint development
calibration froze definition threshold 0.75 and orientation threshold 0.95.
It produced 23 TP, 15 FP, and 36 FN (strict pair F1 0.4742), so the correction
materially changed—and reduced—the Jev result. Candidate coverage remained
47/59 because candidate generation did not change. See
[T059-jev-split-development.json](../../artifacts/T059-jev-split-development.json).

Captured-response tests cover mapping, caching, retry, malformed responses,
budgets, threshold tie-breaking, Unicode, and registry creation. The final
repository gate passed with 408 tests, one optional skip, Ruff, strict mypy,
and 95.18% coverage.
