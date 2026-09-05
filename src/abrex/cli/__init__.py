"""Command-line adapters for the abbreviation-resolution platform."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from abrex.config import (
    ConfigError,
    load_resolved_config,
    serialize_resolved_config,
)
from abrex.corpora import (
    CanonicalSerializationError,
    CorpusError,
    DatasetManifest,
    corpus_config_from_resolved,
    create_corpus_pipeline,
    fingerprint_records,
    load_corpus_build_groups,
    read_canonical_jsonl,
    write_canonical_dataset,
)
from abrex.registry import RegistryError
from abrex.resolvers import (
    PredictionSerializationError,
    ResolverError,
    create_resolver_executor,
    resolver_config_from_resolved,
    write_prediction_artifact,
)
from abrex.tools.download_datasets import (
    DownloadError,
    download_datasets,
    load_download_config,
    results_to_json,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abrex")
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="configuration commands")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    resolve = config_commands.add_parser(
        "resolve", help="merge, interpolate, validate, and print YAML configuration"
    )
    resolve.add_argument(
        "paths", nargs="+", type=Path, help="YAML layers in precedence order"
    )
    resolve.add_argument(
        "--format", choices=("yaml", "json"), default="yaml", dest="output_format"
    )
    corpus = commands.add_parser("corpus", help="canonical corpus commands")
    corpus_commands = corpus.add_subparsers(dest="corpus_command", required=True)
    build = corpus_commands.add_parser(
        "build", help="build and serialize a canonical corpus artifact"
    )
    build.add_argument(
        "paths", nargs="*", type=Path, help="YAML layers in precedence order"
    )
    build.add_argument("--config", type=Path, help="one corpus YAML configuration")
    build.add_argument(
        "--output", type=Path, help="canonical JSONL path (overrides YAML output)"
    )
    build.add_argument(
        "--manifest", type=Path, help="manifest path (defaults beside JSONL output)"
    )
    build_all = corpus_commands.add_parser(
        "build-all", help="build every corpus configuration in a named group"
    )
    build_all.add_argument("--group", required=True, help="configured group name")
    build_all.add_argument(
        "--groups-config",
        type=Path,
        default=Path("configs/corpus-groups.yaml"),
        help="YAML group manifest",
    )
    resolver = commands.add_parser("resolver", help="resolver execution commands")
    resolver_commands = resolver.add_subparsers(dest="resolver_command", required=True)
    run = resolver_commands.add_parser(
        "run", help="run a configured resolver over canonical documents"
    )
    run.add_argument(
        "paths", nargs="+", type=Path, help="YAML layers in precedence order"
    )
    run.add_argument("--input", required=True, type=Path, help="canonical JSONL input")
    run.add_argument(
        "--output", required=True, type=Path, help="prediction JSONL output"
    )
    datasets = commands.add_parser("datasets", help="historical dataset utilities")
    dataset_commands = datasets.add_subparsers(dest="datasets_command", required=True)
    download = dataset_commands.add_parser(
        "download", help="download configured dataset sources"
    )
    download.add_argument("config", type=Path, help="YAML download manifest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    args = _build_parser().parse_args(argv)
    if args.command == "config" and args.config_command == "resolve":
        try:
            config = load_resolved_config(args.paths)
            sys.stdout.write(
                serialize_resolved_config(config, format=args.output_format)
            )
        except ConfigError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0
    if args.command == "datasets" and args.datasets_command == "download":
        try:
            results = download_datasets(load_download_config(args.config))
            sys.stdout.write(results_to_json(results))
        except DownloadError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0
    if args.command == "corpus" and args.corpus_command == "build":
        try:
            config_paths = _select_corpus_config_paths(args.config, args.paths)
            manifest = _build_corpus(config_paths, args.output, args.manifest)
            sys.stdout.write(manifest.to_json())
        except (
            ConfigError,
            CorpusError,
            CanonicalSerializationError,
            RegistryError,
            ValueError,
        ) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0
    if args.command == "corpus" and args.corpus_command == "build-all":
        try:
            groups = load_corpus_build_groups(args.groups_config)
            manifests = [
                _build_corpus((config_path,), None, None)
                for config_path in groups.paths_for(args.group)
            ]
            sys.stdout.write(
                json.dumps(
                    [manifest.to_dict() for manifest in manifests],
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        except (
            ConfigError,
            CorpusError,
            CanonicalSerializationError,
            RegistryError,
            ValueError,
        ) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0
    if args.command == "resolver" and args.resolver_command == "run":
        try:
            config = load_resolved_config(args.paths)
            resolver_config = resolver_config_from_resolved(config)
            executor = create_resolver_executor(resolver_config)
            records = read_canonical_jsonl(args.input)
            resolver_result = executor.resolve_documents(
                tuple(record.document for record in records)
            )
            dataset_fingerprint = fingerprint_records(records)
            fingerprint = write_prediction_artifact(
                resolver_result,
                args.output,
                dataset_fingerprint=dataset_fingerprint,
            )
            sys.stdout.write(
                f'{{"fingerprint":"{fingerprint}","record_count":'
                f"{len(resolver_result.records)},"
                f'"resolver":"{resolver_result.resolver.key}"}}\n'
            )
        except (
            ConfigError,
            CanonicalSerializationError,
            PredictionSerializationError,
            RegistryError,
            ResolverError,
            ValueError,
        ) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0
    raise AssertionError("argparse accepted an unsupported command")  # pragma: no cover


def _select_corpus_config_paths(
    config: Path | None, paths: Sequence[Path]
) -> tuple[Path, ...]:
    """Combine the explicit ``--config`` shorthand with optional YAML layers."""

    selected = ((config,) if config is not None else ()) + tuple(paths)
    if not selected:
        raise ConfigError("corpus build requires --config or at least one YAML path")
    return selected


def _build_corpus(
    config_paths: Sequence[Path], output: Path | None, manifest_path: Path | None
) -> DatasetManifest:
    """Run the generic configured corpus pipeline and canonical serializer."""

    config = load_resolved_config(config_paths)
    corpus_config = corpus_config_from_resolved(config)
    corpus_result = create_corpus_pipeline(corpus_config).build(
        corpus_config.source.to_resource()
    )
    config_fingerprint = hashlib.sha256(
        serialize_resolved_config(config, format="json").encode("utf-8")
    ).hexdigest()
    configured_output = corpus_config.output
    if output is None:
        if configured_output is None:
            raise ConfigError(
                "corpus configuration must declare output when --output is omitted"
            )
        output = configured_output.jsonl_path
        manifest_path = manifest_path or configured_output.manifest_path
    output.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return write_canonical_dataset(
        corpus_result,
        output,
        manifest_path=manifest_path,
        mode="strict" if corpus_config.strict else "permissive",
        config_fingerprint=config_fingerprint,
    )


__all__ = ["main"]
