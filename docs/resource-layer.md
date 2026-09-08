# Local abbreviation resource layer

T028 provides a typed, SQLite-backed query boundary for local aggregate
frequency resources. The first adapter reads the supplied gzip-compressed JSON
shape `{SF: {LF: count}}` incrementally and can be bounded with
`max_entries`:

```console
python -m abrex config resolve configs/resources/T028-frequency-pilot.yaml
```

Use the Python API to import and query the resource:

```python
from pathlib import Path

from abrex.resources import load_frequency_config, import_frequency_resource

config = load_frequency_config(Path("configs/resources/T028-frequency-pilot.yaml"))
resource = import_frequency_resource(config)
variants = resource.lookup("TNF")
```

Rows retain raw SF/LF forms, the declared normalized keys, count, count-unit,
source label and source SHA-256. `identity` preserves case and punctuation;
`casefold` is the only alternative and does not collapse raw rows. Repeated
source rows remain separate. Aggregate counts are not document counts, so
`document_frequency` always returns unknown (`None`) until article links are
available from the literature pipeline. No gold label or automatic UMLS
acquisition is implied.
