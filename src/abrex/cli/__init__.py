"""Command-line adapters for the abbreviation-resolution platform."""

from __future__ import annotations

import argparse
import hashlib
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
    corpus_config_from_resolved,
    create_corpus_pipeline,
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
        "paths", nargs="+", type=Path, help="YAML layers in precedence order"
    )
    build.add_argument(
        "--output", required=True, type=Path, help="canonical JSONL path"
    )
    build.add_argument(
        "--manifest", type=Path, help="manifest path (defaults beside JSONL output)"
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
    if args.command == "corpus" and args.corpus_command == "build":
        try:
            config = load_resolved_config(args.paths)
            corpus_config = corpus_config_from_resolved(config)
            corpus_result = create_corpus_pipeline(corpus_config).build(
                corpus_config.source.to_resource()
            )
            config_fingerprint = hashlib.sha256(
                serialize_resolved_config(config, format="json").encode("utf-8")
            ).hexdigest()
            manifest = write_canonical_dataset(
                corpus_result,
                args.output,
                manifest_path=args.manifest,
                mode="strict" if corpus_config.strict else "permissive",
                config_fingerprint=config_fingerprint,
            )
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
    if args.command == "resolver" and args.resolver_command == "run":
        try:
            config = load_resolved_config(args.paths)
            resolver_config = resolver_config_from_resolved(config)
            executor = create_resolver_executor(resolver_config)
            records = read_canonical_jsonl(args.input)
            resolver_result = executor.resolve_documents(
                tuple(record.document for record in records)
            )
            fingerprint = write_prediction_artifact(resolver_result, args.output)
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


__all__ = ["main"]
