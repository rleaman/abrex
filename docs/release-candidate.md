# ABREX local release candidate

The local release candidate is an installable Python 3.13 package with the
lightweight default dependencies declared in `pyproject.toml`. Verify it
without network access after the build backend and development dependencies
are installed:

```powershell
py -3.13 scripts/quality_gate.py --full
py -3.13 scripts/verify_wheel.py --work-dir .pytest-tmp
```

The first command tests the current checkout and reports its exact package
origin. The second command builds and installs into a disposable environment;
it does not reinstall `abrex` into the development environment. Its offline
smoke covers local document resolution, the toy experiment with an isolated
output root, and a local SQLite resource query. It reports the wheel package
origin and verifies the source origin again after cleanup.

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
