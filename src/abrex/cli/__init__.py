"""Command-line adapters for the abbreviation-resolution platform."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from abrex.config import (
    ConfigError,
    load_config_layer,
    load_resolved_config,
    serialize_resolved_config,
)
from abrex.corpora import (
    AnnotationPilotError,
    CanonicalSerializationError,
    CorpusError,
    DatasetManifest,
    corpus_config_from_resolved,
    create_corpus_pipeline,
    fingerprint_records,
    load_annotation_config,
    load_corpus_build_groups,
    read_canonical_jsonl,
    run_annotation_pilot,
    write_canonical_dataset,
)
from abrex.experiments import ExperimentError, run_experiment
from abrex.literature import (
    AcquisitionError,
    ArticleError,
    ArticleParseError,
    ArticleSerializationError,
    CorpusSelectionError,
    PilotConfig,
    PilotError,
    SamplingError,
    acquire_pubmed,
    article_to_dict,
    create_article_resolution_service,
    estimate_acquisition,
    load_acquisition_config,
    load_corpus_selection_config,
    load_sampling_config,
    parse_bioc_json,
    parse_pubmed_xml,
    read_article_json,
    replay_acquisition,
    run_pilot,
    sample_frame,
    select_corpus,
    serialize_article_resolution,
    write_corpus_selection_manifest,
    write_sampling_manifest,
)
from abrex.logging import configure_logging
from abrex.registry import RegistryError
from abrex.resolvers import (
    PredictionSerializationError,
    ResolverError,
    create_resolver_executor,
    resolver_config_from_resolved,
    write_prediction_artifact,
)
from abrex.resources import (
    AdamAcquisitionError,
    AllieAcquisitionError,
    acquire_allie,
    import_adam,
    load_adam_config,
    load_allie_config,
)
from abrex.tools.download_datasets import (
    DatasetDownloadsConfig,
    DownloadError,
    download_datasets,
    load_download_config,
    load_download_groups,
    results_to_json,
    validate_download_selection,
)

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abrex")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--quiet", action="store_true", help="show warnings and errors only"
    )
    verbosity.add_argument(
        "--verbose", action="store_true", help="show normal operational progress"
    )
    verbosity.add_argument(
        "--debug", action="store_true", help="enable diagnostic logging"
    )
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
    download.add_argument(
        "paths", nargs="*", type=Path, help="legacy YAML download manifest"
    )
    download.add_argument("--config", type=Path, help="one YAML download bundle")
    download.add_argument(
        "--dry-run",
        action="store_true",
        help="classify items without network or writes",
    )
    download.add_argument(
        "--force", action="store_true", help="replace existing conflicting artifacts"
    )
    download_all = dataset_commands.add_parser(
        "download-all", help="download every bundle in a named group"
    )
    download_all.add_argument("--group", required=True, help="configured group name")
    download_all.add_argument(
        "--groups-config",
        type=Path,
        default=Path("configs/dataset-groups.yaml"),
        help="YAML dataset group manifest",
    )
    download_all.add_argument(
        "--dry-run",
        action="store_true",
        help="classify items without network or writes",
    )
    download_all.add_argument(
        "--force", action="store_true", help="replace existing conflicting artifacts"
    )
    literature = commands.add_parser(
        "literature", help="bounded literature acquisition utilities"
    )
    literature_commands = literature.add_subparsers(
        dest="literature_command", required=True
    )
    acquire = literature_commands.add_parser(
        "acquire", help="acquire fixed PubMed IDs into immutable raw files"
    )
    acquire.add_argument("config", type=Path, help="YAML acquisition manifest")
    acquire.add_argument(
        "--dry-run",
        action="store_true",
        help="estimate requests and bytes without network access",
    )
    replay = literature_commands.add_parser(
        "replay", help="validate an acquisition manifest and raw files offline"
    )
    replay.add_argument("manifest", type=Path)
    sample = literature_commands.add_parser(
        "sample", help="build a deterministic contemporary sampling proposal"
    )
    sample.add_argument("--config", required=True, type=Path)
    sample.add_argument(
        "--frame", type=Path, help="override the configured JSONL frame"
    )
    sample.add_argument("--output", type=Path)
    select = literature_commands.add_parser(
        "select", help="freeze a deterministic bounded corpus-selection manifest"
    )
    select.add_argument("--config", required=True, type=Path)
    select.add_argument(
        "--frame", type=Path, help="override the configured JSONL frame"
    )
    select.add_argument("--output", type=Path)
    pilot = literature_commands.add_parser(
        "pilot", help="run the bounded random PMC/PubMed comparison pilot"
    )
    pilot.add_argument("config", type=Path)
    resources = commands.add_parser(
        "resources", help="external lexical-resource commands"
    )
    resource_commands = resources.add_subparsers(dest="resource_command", required=True)
    allie = resource_commands.add_parser(
        "acquire-allie", help="acquire a bounded official ALLIE REST response"
    )
    allie.add_argument("config", type=Path, help="YAML ALLIE acquisition manifest")
    adam = resource_commands.add_parser(
        "import-adam", help="import a bounded official ADAM tar archive"
    )
    adam.add_argument("config", type=Path, help="YAML ADAM import manifest")
    experiment = commands.add_parser(
        "experiment", help="declarative experiment commands"
    )
    experiment_commands = experiment.add_subparsers(
        dest="experiment_command", required=True
    )
    experiment_run = experiment_commands.add_parser(
        "run", help="run a configured experiment"
    )
    experiment_run.add_argument(
        "paths", nargs="+", type=Path, help="YAML layers in precedence order"
    )
    experiment_run.add_argument("--output-root", type=Path, help="override output.root")
    experiment_run.add_argument(
        "--reuse-cache", action="store_true", help="reuse a validated prediction cache"
    )
    article = commands.add_parser(
        "article", help="resolve locally available PubMed/PMC article data"
    )
    article_commands = article.add_subparsers(dest="article_command", required=True)
    article_resolve = article_commands.add_parser(
        "resolve", help="segment and resolve one local article JSON document"
    )
    article_resolve.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="YAML layers selecting resolver and segmentation",
    )
    article_resolve.add_argument("--input", required=True, type=Path)
    article_resolve.add_argument("--output", type=Path)
    article_convert = article_commands.add_parser(
        "convert", help="convert one local PubMed XML or BioC JSON file to article JSON"
    )
    article_convert.add_argument(
        "--format", choices=("pubmed-xml", "bioc-json"), required=True
    )
    article_convert.add_argument("--input", required=True, type=Path)
    article_convert.add_argument("--output", type=Path)
    article_convert.add_argument("--include-title", action="store_true")
    annotations = commands.add_parser(
        "annotations", help="contemporary annotation-pilot commands"
    )
    annotation_commands = annotations.add_subparsers(
        dest="annotation_command", required=True
    )
    annotation_run = annotation_commands.add_parser(
        "run", help="import annotation cases and write canonical/report artifacts"
    )
    annotation_run.add_argument("config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    args = _build_parser().parse_args(argv)
    level = (
        logging.WARNING
        if args.quiet
        else (logging.DEBUG if args.debug else logging.INFO)
    )
    configure_logging(level)
    logger.debug("Parsed CLI command: %s", args.command)
    if args.command == "config" and args.config_command == "resolve":
        try:
            logger.info(
                "Loading and resolving configuration: %s",
                ", ".join(map(str, args.paths)),
            )
            config = load_resolved_config(args.paths)
            sys.stdout.write(
                serialize_resolved_config(config, format=args.output_format)
            )
        except ConfigError as error:
            logger.error("error: configuration resolution failed: %s", error)
            return 2
        return 0
    if args.command == "datasets" and args.datasets_command in {
        "download",
        "download-all",
    }:
        try:
            configs: tuple[DatasetDownloadsConfig, ...]
            if args.datasets_command == "download":
                selected = ((args.config,) if args.config is not None else ()) + tuple(
                    args.paths
                )
                if not selected:
                    raise DownloadError(
                        "datasets download requires --config or a legacy YAML path"
                    )
                if len(selected) != 1:
                    raise DownloadError(
                        "datasets download accepts exactly one bundle configuration"
                    )
                configs = (load_download_config(selected[0]),)
            else:
                download_groups = load_download_groups(args.groups_config)
                configs = tuple(
                    (
                        load_download_config(path).model_copy(
                            update={"overwrite": False}
                        )
                        if not args.force
                        else load_download_config(path)
                    )
                    for path in download_groups.paths_for(args.group)
                )
            validate_download_selection(configs)
            results = tuple(
                item
                for config in configs
                for item in (
                    download_datasets(config)
                    if not args.dry_run and not args.force
                    else download_datasets(
                        config, dry_run=args.dry_run, force=args.force
                    )
                )
            )
            sys.stdout.write(results_to_json(results))
            return (
                2
                if any(item.status in {"conflict", "failed"} for item in results)
                else 0
            )
        except (DownloadError, ConfigError) as error:
            logger.error("error: dataset download failed: %s", error)
            return 2
    if args.command == "literature" and args.literature_command == "acquire":
        try:
            acquisition_config = load_acquisition_config(args.config)
            if args.dry_run:
                sys.stdout.write(
                    json.dumps(
                        estimate_acquisition(acquisition_config).to_dict(),
                        sort_keys=True,
                    )
                    + "\n"
                )
            else:
                sys.stdout.write(
                    json.dumps(
                        acquire_pubmed(acquisition_config).to_dict(), sort_keys=True
                    )
                    + "\n"
                )
        except (AcquisitionError, OSError, ValueError) as error:
            logger.error("error: literature acquisition failed: %s", error)
            return 2
        return 0
    if args.command == "literature" and args.literature_command == "replay":
        try:
            sys.stdout.write(
                json.dumps(replay_acquisition(args.manifest), sort_keys=True) + "\n"
            )
        except (AcquisitionError, OSError, ValueError) as error:
            logger.error("error: literature replay failed: %s", error)
            return 2
        return 0
    if args.command == "literature" and args.literature_command == "sample":
        try:
            sampling_config = load_sampling_config(args.config)
            sampling_result = sample_frame(sampling_config, frame_path=args.frame)
            output = args.output or sampling_config.manifest_path
            fingerprint = write_sampling_manifest(sampling_result, output)
            sys.stdout.write(
                json.dumps(
                    {
                        "manifest": str(output),
                        "fingerprint": fingerprint,
                        "summary": sampling_result.summary,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        except (OSError, SamplingError, ValueError) as error:
            logger.error("error: literature sampling failed: %s", error)
            return 2
        return 0
    if args.command == "literature" and args.literature_command == "select":
        try:
            selection_config = load_corpus_selection_config(args.config)
            selection_result = select_corpus(selection_config, frame_path=args.frame)
            output = args.output or selection_config.manifest_path
            fingerprint = write_corpus_selection_manifest(selection_result, output)
            sys.stdout.write(
                json.dumps(
                    {
                        "manifest": str(output),
                        "fingerprint": fingerprint,
                        "summary": selection_result.summary,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        except (CorpusSelectionError, OSError, ValueError) as error:
            logger.error("error: corpus selection failed: %s", error)
            return 2
        return 0
    if args.command == "resources" and args.resource_command == "acquire-allie":
        try:
            allie_result = acquire_allie(load_allie_config(args.config))
            sys.stdout.write(json.dumps(allie_result.to_dict(), sort_keys=True) + "\n")
        except (AllieAcquisitionError, OSError, ValueError) as error:
            logger.error("error: ALLIE acquisition failed: %s", error)
            return 2
        return 0
    if args.command == "resources" and args.resource_command == "import-adam":
        try:
            adam_result = import_adam(load_adam_config(args.config))
            sys.stdout.write(json.dumps(adam_result.to_dict(), sort_keys=True) + "\n")
        except (AdamAcquisitionError, OSError, ValueError) as error:
            logger.error("error: ADAM import failed: %s", error)
            return 2
        return 0
    if args.command == "experiment" and args.experiment_command == "run":
        try:
            logger.info("Starting experiment run")
            result = run_experiment(
                tuple(args.paths),
                output_root=args.output_root,
                reuse_cached_predictions=True if args.reuse_cache else None,
            )
            sys.stdout.write(
                json.dumps(
                    {
                        "run_directory": str(result.run_directory),
                        "manifest": str(result.manifest_path),
                        "prediction_fingerprint": result.prediction_fingerprint,
                        "evaluation_fingerprint": result.evaluation_fingerprint,
                        "reused_predictions": result.reused_predictions,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        except (
            ConfigError,
            ExperimentError,
            CanonicalSerializationError,
            PredictionSerializationError,
            RegistryError,
            ResolverError,
            ValueError,
        ) as error:
            logger.error("error: experiment failed: %s", error)
            return 2
        return 0
    if args.command == "article" and args.article_command == "resolve":
        try:
            config = load_resolved_config(tuple(args.paths))
            service = create_article_resolution_service(config)
            article_result = service.resolve(read_article_json(args.input))
            serialized = serialize_article_resolution(article_result)
            if args.output is None:
                sys.stdout.write(serialized)
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(serialized, encoding="utf-8", newline="\n")
                sys.stdout.write(
                    json.dumps(
                        {
                            "article_id": article_result.article_id,
                            "entity_count": len(article_result.entities),
                            "output": str(args.output),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        except (
            ConfigError,
            ArticleError,
            ArticleSerializationError,
            OSError,
            RegistryError,
            ResolverError,
            ValueError,
        ) as error:
            logger.error("error: article resolution failed: %s", error)
            return 2
        return 0
    if args.command == "literature" and args.literature_command == "pilot":
        try:
            raw = load_config_layer(args.config)
            section = raw.get("literature_pilot")
            if not isinstance(section, dict):
                raise PilotError("configuration requires a literature_pilot mapping")
            report = run_pilot(PilotConfig.model_validate(section))
            sys.stdout.write(json.dumps(report["counts"], sort_keys=True) + "\n")
        except (PilotError, OSError, ValueError, json.JSONDecodeError) as error:
            logger.error("error: literature pilot failed: %s", error)
            return 2
        return 0
    if args.command == "article" and args.article_command == "convert":
        try:
            payload = args.input.read_bytes()
            parsed = (
                parse_pubmed_xml(payload, include_title=args.include_title)
                if args.format == "pubmed-xml"
                else parse_bioc_json(payload, include_title=args.include_title)
            )
            serialized = (
                json.dumps(
                    article_to_dict(parsed.article),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            if args.output is None:
                sys.stdout.write(serialized)
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(serialized, encoding="utf-8", newline="\n")
                sys.stdout.write(
                    json.dumps(
                        {
                            "article_id": parsed.article.stable_id,
                            "diagnostic_count": len(parsed.diagnostics),
                            "output": str(args.output),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        except (ArticleParseError, OSError, ValueError) as error:
            logger.error("error: article conversion failed: %s", error)
            return 2
        return 0
    if args.command == "annotations" and args.annotation_command == "run":
        try:
            report = run_annotation_pilot(load_annotation_config(args.config))
            sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
        except (AnnotationPilotError, OSError, ValueError) as error:
            logger.error("error: annotation pilot failed: %s", error)
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
            logger.error("error: corpus build failed: %s", error)
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
            logger.error("error: corpus group build failed: %s", error)
            return 2
        return 0
    if args.command == "resolver" and args.resolver_command == "run":
        try:
            logger.info(
                "Loading resolver configuration: %s", ", ".join(map(str, args.paths))
            )
            config = load_resolved_config(args.paths)
            resolver_config = resolver_config_from_resolved(config)
            executor = create_resolver_executor(resolver_config)
            records = read_canonical_jsonl(args.input)
            resolver_result = executor.resolve_documents(
                tuple(record.document for record in records)
            )
            dataset_fingerprint = fingerprint_records(records)
            args.output.parent.mkdir(parents=True, exist_ok=True)
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
            OSError,
            ValueError,
        ) as error:
            logger.error("error: resolver run failed: %s", error)
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

    logger.info("Loading corpus configuration: %s", ", ".join(map(str, config_paths)))
    config = load_resolved_config(config_paths)
    corpus_config = corpus_config_from_resolved(config)
    logger.info("Starting corpus build with adapter %s", corpus_config.adapter.type)
    logger.info("Reading raw source")
    corpus_result = create_corpus_pipeline(corpus_config).build(
        corpus_config.source.to_resource()
    )
    logger.info("Parsed and normalized %d records", len(corpus_result.records))
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
    manifest = write_canonical_dataset(
        corpus_result,
        output,
        manifest_path=manifest_path,
        mode="strict" if corpus_config.strict else "permissive",
        config_fingerprint=config_fingerprint,
    )
    logger.info(
        "Wrote canonical artifact %s (%d records); dataset fingerprint: %s",
        output,
        manifest.record_count,
        manifest.fingerprint,
    )
    return manifest


__all__ = ["main"]
