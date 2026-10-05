# T065 completion: fresh sample and blind packet

Completed October 4, 2026 local time after the scientific lead approved T063
without revision.

## Delivered

- Frozen T063 decision SHA-256:
  `08eba6fd0adae99c355a6a18e8c615a037171056cf135c8339f8f3092a732541`.
- Typed deterministic source-only sampling and linked-identity exclusion logic.
- A bounded NCBI acquisition using seed `20261002`: 37 article draws, 29
  documented exclusions, eight selected groups, zero fetch failures, 4,695,175
  bytes, and no reached time/byte/request limit.
- A prediction-free 32-case packet with 12 PMC prose passages, 12 PubMed
  abstract passages, eight table/list sections, and exactly four cases per
  article group.
- An empty annotation state, source manifest, exact license/source hashes,
  one-command T066 PowerShell launcher, and concise reviewer guide.
- Actual-packet Microsoft Edge QA showing all 32 cases load, the from-scratch
  relation control is available, no prediction fields are exposed, and no
  annotation or lock state is created by QA.

## Blindness boundary

No evaluated resolver, Jev call, candidate generator, or abbreviation-token
enrichment ran on the fresh sources. T067 remains prohibited until the user
completes T066 and creates the immutable annotation lock.

## Verification

- focused T065 unit tests: 5 passed;
- Ruff and strict mypy passed for the new typed sampling core;
- source, packet, state, and raw-source hashes replay successfully;
- actual-packet Edge QA passed.
