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

The currently available local sources are Ab3P, BIOADI, MEDSTRACT, and
Schwartz & Hearst/BioText. Corrected BADREX sources and SDU shared-task files
are listed by the download manifest but are not configured until their source
files are present locally; this avoids committing configurations that cannot
run.
