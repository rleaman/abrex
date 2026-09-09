# T051 random-literature comparison pilot

Status: Partial real-run delivery; acquisition target satisfied, strict
three-primary-method comparison unavailable on this host.

The reproducible command was:

```powershell
$env:PYTHONPATH = "src;env313/Lib/site-packages"
py -3.13 -m abrex literature pilot configs/literature/T051-random-pilot.yaml
```

The repaired v2 run produced 10 verified exact CC BY PMC full texts and 20
unique PubMed records with nonempty abstracts. The manifest recorded 74 bounded
attempts, 44 exclusions, 3,806,317 downloaded bytes and 1,567 section
inventories. Each selected PMC article has raw JATS and Unicode BioC snapshots,
source hashes, license evidence, parser diagnostics and section/structure
metadata. Manifest SHA-256 is
`613d4b35d38f2659ebddf2d8055f354ce9dc0b6f0a560914c66d06bb92c2f9fa`.

Schwartz–Hearst ran on the selected canonical sections. Ab3P and PLODv2 were
diagnosed dynamically as unavailable/failed from their configured workers, and
the transparent hybrid recorded explicit primary-method-incomplete failures.
No accuracy claims were made.

Tracked summary: [T051-random-pilot-summary.json](../../artifacts/T051-random-pilot-summary.json). Raw artifacts remain under ignored `.artifacts/T051/random-pilot-v2/` and are replayable from `pilot-manifest.json`.
