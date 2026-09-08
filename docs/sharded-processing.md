# Resumable bounded corpus processing

`abrex.experiments.run_sharded` is the infrastructure boundary for large
document pilots. It routes documents by a SHA-256 document-ID shard function,
writes bounded disk-backed input buffers, processes one shard at a time, and
publishes each output through a `.part` rename. The complete run manifest is
published last; partial files never authorize cache reuse.

```python
from abrex.domain import Document
from abrex.experiments import ShardedProcessingConfig, run_sharded

config = ShardedProcessingConfig(
    output_root="artifacts/sharded",
    shard_count=16,
    retry_limit=2,
    source_identity="pubmed-manifest-sha256",
    processor_identity="resolver-key@version",
    configuration_identity="resolved-config-sha256",
)
result = run_sharded(
    (Document("id-1", "text"),),
    lambda document: {"prediction_count": 0},
    config,
    input_fingerprint="source-content-sha256",
)
```

The identity includes source, processor, configuration, input fingerprint and
shard count. Failed documents are quarantined with their input fingerprint and
error type; they are not converted to successful empty predictions. The
manifest records processed/failed counts, elapsed time, output bytes and an
explicit peak-memory measurement field. Production-scale limits and hardware
forecasts remain campaign decisions owned by later tasks.
