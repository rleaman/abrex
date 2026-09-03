"""Command-line adapters for the abbreviation-resolution platform."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from abrex.config import (
    ConfigError,
    load_resolved_config,
    serialize_resolved_config,
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
    raise AssertionError("argparse accepted an unsupported command")  # pragma: no cover


__all__ = ["main"]
