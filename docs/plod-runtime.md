# PLODv2 CPU runtime: T023 prerequisite supplied

Verified September 7, 2026. The missing runtime/checkpoint blocker is resolved;
T023's detector integration and acceptance tests still need implementation.

## Use the installed worker

Ubuntu WSL has a separate optional environment, leaving the core ABREX/Ab3P
environment unchanged:

- Interpreter: `/home/rleaman/.local/share/abrex/plod313/bin/python`.
- Python 3.13.15, Flair 0.15.1, PyTorch 2.14.0+cpu.
- ABREX is installed editable from the working checkout; Pydantic is installed.
- Exact dependency snapshot: [plod-runtime-requirements.txt](artifacts/plod-runtime-requirements.txt).
- Dependency consistency check: all installed packages compatible.

The repository fast gate was attempted after setup but stopped at formatting
checks in concurrently modified CLI/literature files. Those files were left
untouched. The runtime checks above are successful; no passing repository-wide
gate or completed T023 implementation is claimed by this setup.

From PowerShell, rerun the local setup smoke:

```powershell
wsl.exe -d Ubuntu -- bash -lc '"$HOME/.local/share/abrex/plod313/bin/python" /mnt/c/Users/mail/Documents/Projects/abrex/.artifacts/plod-runtime/smoke.py'
```

The smoke script is a local setup artifact, not the finished T023 detector.
Its machine-readable [result](artifacts/plod-runtime-smoke.json) is checked in.
Use this Python for subsequent PLOD work rather than bare WSL `python3` or the
core `venv313` interpreter. No CUDA installation is needed for this CPU pilot.

## Model identity and location

- Publisher: [surrey-nlp/flair-abbr-pubmed-filtered](https://huggingface.co/surrey-nlp/flair-abbr-pubmed-filtered).
- Pinned revision: `019ed5392cad2deab220ad6bfda0681b20cabe21`.
- Local checkpoint:
  `/home/rleaman/.local/share/abrex/models/plodv2/019ed5392cad2deab220ad6bfda0681b20cabe21/pytorch_model.bin`.
- Size: 394,150,307 bytes.
- SHA-256: `3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277`.
  This matches the publisher's LFS metadata for the pinned revision.
- The publisher's README is saved next to the weights. The model card declares
  CC-BY-SA-4.0; weights are not added to Git or redistributed by this setup.

Load using `SequenceTagger.load()` with the local checkpoint path. Do not use
an unpinned model-name download during inference.

## Verified behavior and implementation guidance

The three-sentence CPU pilot detected both LF and AC spans for TNF and MRI,
and no spans for `The patient was stable.` All emitted offsets sliced back
to the exact input text. Loading and prediction also passed with Python socket
connections blocked. No additional embedding downloads were needed.

The checkpoint contains stacked PubMed forward/backward Flair embeddings.
Their displayed names retain the author's `/user/HS501/...` paths; these are
not missing local files that need to be recreated. The successful offline load
provides evidence that this checkpoint contains the required embedding state.

The tagger's label type is `ner`, with decoded span labels `AC` and `LF`.
Its internal dictionary uses BIOES tags plus start/stop labels. T023 must map
`AC` explicitly to the short-form concept and preserve scores as span scores.
No pairing, long-document policy, Unicode boundary suite, or ABREX span-cache
behavior was implemented by this setup. Those remain T023/T024 work.

The standalone smoke limits PyTorch to two CPU threads and sets Flair's device
to CPU in its own process. Preserve the project's isolation requirements when
designing the actual worker. No Python 3.12 fallback was necessary.

## Recreate the environment

Inside Ubuntu, use a new environment path if preserving the working install:

```bash
cd /mnt/c/Users/mail/Documents/Projects/abrex
uv_tool="$HOME/.local/share/abrex/bin/uv"
plod_env="$HOME/.local/share/abrex/plod313"
"$uv_tool" venv --python 3.13.15 "$plod_env"
"$uv_tool" pip install --python "$plod_env/bin/python" --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match -r docs/artifacts/plod-runtime-requirements.txt
"$uv_tool" pip install --python "$plod_env/bin/python" --no-deps --editable .
```

The requirements snapshot pins all packages; the additional index supplies the
explicit `+cpu` PyTorch wheel. Keep this optional stack separate from the core
development lock. The model download is a separate acquisition step, using the
pinned revision and verifying the SHA-256 above before loading.
