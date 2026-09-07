# Returning to abrex

Run commands from the repository root in PowerShell. Set the interpreter once
per terminal session:

```powershell
$py = ".\env313\Scripts\python.exe"
```

If that file is missing, follow [environment setup](development-environments.md).
On Linux or in an activated environment, replace `& $py` with `python`.
The examples below write generated results under ignored `data/exploration/`;
keep any results you need separately from Git. Reusing an explicit output file
can replace its previous contents.

## Choose a starting point

| What I want | Where to start | What I get |
| --- | --- | --- |
| Check that the pipeline runs | Tiny experiment below | Predictions, evaluation, run metadata |
| See real abbreviation extractions | MEDSTRACT resolver run below | SF/LF predictions and diagnostics |
| Understand corpus exclusions and repairs | [Existing audit](artifacts/historical-corpus-audit.json) | Counts, fingerprints, diagnostic summaries |
| Review source semantics | [Corpus inventory](historical-corpus-inventory.md) | Annotation units and eligible metrics |
| Find the next implementation task | [Task index](tasks/README.md), then its completion notes | Dependencies and current status |

## Tiny experiment: no external data required

```powershell
& $py -m abrex experiment run docs/examples/experiment-toy.yaml --output-root data/exploration/toy-experiment
```

The command reports artifact locations. Open `evaluation.json` for scores and
`run-manifest.json` for configuration and provenance. Predictions and reports
are saved as separate artifacts. These bundled examples demonstrate plumbing,
not scientific benchmark performance.

Run the same example with the dependency-free Schwartz–Hearst resolver by
layering its configuration after the experiment configuration:

```powershell
& $py -m abrex experiment run docs/examples/experiment-toy.yaml docs/examples/resolver-schwartz-hearst.yaml --output-root data/exploration/sh-experiment
```

## Real corpus: inspect predicted definitions

Once the MEDSTRACT source is available, build its canonical representation if
needed:

```powershell
& $py -m abrex corpus build --config configs/corpora/medstract.yaml
```

Then extract definitions:

```powershell
& $py -m abrex resolver run docs/examples/resolver-schwartz-hearst.yaml --input data/processed/medstract/canonical.jsonl --output data/exploration/medstract-sh-predictions.jsonl
```

The JSONL has one prediction record per line, with predicted definitions and
diagnostics. This command does not evaluate accuracy. Substitute `ab3p`,
`bioadi`, or `schwartz_hearst` in the input directory to use another built
paired corpus, and choose a different output filename for each.

If raw data are absent, see [historical downloads](historical-downloads.md).
If canonical data are absent, see [historical builds](historical-builds.md).
Building regenerates the configured canonical files and manifests.

## Corpus audit: understand what survived conversion

Read the [existing audit](artifacts/historical-corpus-audit.json) first.
To regenerate a report for MEDSTRACT:

```powershell
& $py scripts/audit_historical_corpora.py --output data/exploration/medstract-audit.json configs/corpora/medstract.yaml
```

Omit the final configuration argument to audit all configured historical
corpora. The audit also rebuilds their canonical files and manifests. It
records raw/canonical counts, source fingerprints, diagnostic counts, and
metric eligibility; inspect each entry's status for missing or failed sources.
Full diagnostics remain in the processed manifests.

The BADREX-corrected variants are [settled exclusions](badrex-availability.md).
Their absence needs no further investigation.

## Evaluation and external tools

Use `experiment run` for the complete evaluation workflow. Merely running a
resolver does not produce scores. [Evaluation documentation](evaluation.md)
describes exact-pair versus independent-span metrics and available JSON, TSV,
and HTML error reporters. Corpus-building YAML and experiment YAML serve
different interfaces; do not use a corpus build config as an experiment config.

The Schwartz–Hearst commands above run directly on Windows. Real Ab3P runs
under Ubuntu/WSL and needs its executable and WordData resources; follow
[the Ab3P setup](development-environments.md#real-ab3p-in-ubuntu-wsl2) and
[resolver documentation](resolvers.md) for runtime/cache configuration.

## Command reminders

```powershell
& $py -m abrex --help
& $py -m abrex resolver run --help
& $py -m abrex experiment run --help
```

For more operational detail, place `--debug` before the command group, for
example `& $py -m abrex --debug experiment run docs/examples/experiment-toy.yaml`.
