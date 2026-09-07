# Historical corpus builds

Historical sources are user-managed raw data. Building is a separate local
operation and never occurs as a side effect of downloading.

Run these commands from the repository root after the corresponding source has
been downloaded or otherwise placed under `data/raw/historical/`:

```console
abrex corpus build --config configs/corpora/ab3p.yaml
abrex corpus build --config configs/corpora/bioadi.yaml
abrex corpus build --config configs/corpora/medstract.yaml
abrex corpus build --config configs/corpora/schwartz_hearst.yaml
abrex corpus build --config configs/corpora/sdu_aaai21_ai.yaml
abrex corpus build --config configs/corpora/sdu_aaai21_ad.yaml
abrex corpus build --config configs/corpora/sdu_aaai22_ae.yaml
```

Each command uses the shared adapter, normalization, validation, and T004
canonical serialization path. It writes `canonical.jsonl` and `manifest.json`
under the configured `data/processed/<corpus-or-variant>/` directory.

The configuration-driven convenience command composes the same single-corpus
operation for all currently available historical corpora:

```console
abrex corpus build-all --group historical
```

The group is declared in
[`configs/corpus-groups.yaml`](../configs/corpus-groups.yaml), so adding a
corpus to an orchestration group does not require changing the CLI.

The intended workflow is:

```text
download historical data
    -> build canonical corpora
    -> run resolver
    -> evaluate
```

The raw sources remain user-managed and are not committed. The checked-in
configurations cover the currently available original BioC corpora and SDU
variants. BADREX references in older completion notes describe a historical
local state; the current BADREX sources return 404 and no BADREX configs are
present. A build is expected to fail clearly until its
corresponding downloaded source is present.

SDU@AAAI-21 AD preserves the expansion as text when it is not present in the
sentence, so it does not fabricate a document span. SDU@AAAI-22 AE passes the
source's half-open character endpoints directly to ABREX half-open spans. Its
acronym and long-form lists are independent, so the adapter preserves each
span separately and does not infer pairings from list order. Use the
`exact_span`/`span_prf` evaluation components for this corpus; `exact_pair`
cannot score its intentionally unpaired source annotations.
