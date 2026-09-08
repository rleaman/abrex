# ABREX local release candidate

The local release candidate is an installable Python 3.13 package with the
lightweight default dependencies declared in `pyproject.toml`. Build and
verify it without network access after the build backend is installed:

```powershell
$py = ".\env313\Scripts\python.exe"
& $py -m pip wheel --no-deps --no-build-isolation . --wheel-dir .artifacts/T045/wheel
& $py -m pip install --force-reinstall --no-deps .artifacts/T045/wheel/abrex-0.1.0-py3-none-any.whl
& $py -m abrex config resolve configs/benchmarks/T040-campaign-protocol.yaml
```

The package can resolve local documents and query local SQLite resources.
Optional Ab3P, PLODv2, BioADI, ADAM and ALLIE integrations retain their own
source/runtime manifests; no model weights, raw literature or acquired
archives are included in the wheel.

The release manifest records the wheel hash, quality evidence, research
artifact identities and limitations. T042's work-scale tagged corpus is not
present because its source snapshot, reuse permissions and cost envelope
still require approval. T044's downstream impact is contract/fixture-only
because no user pipeline or frozen dataset is available. These are not
relabelled as completed research claims.
