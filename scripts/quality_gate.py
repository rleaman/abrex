"""Run the repository's fail-fast, offline quality gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

Command = tuple[str, ...]


def run_command(command: Command, *, cwd: Path) -> int:
    """Run one command and return its exact exit status."""
    print(f"+ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    return result.returncode


def run_gate(commands: Sequence[Command], *, root: Path, basetemp_name: str) -> int:
    """Create pytest's parent directory and stop at the first failed command."""
    (root / ".pytest-tmp").mkdir(parents=True, exist_ok=True)
    for command in commands:
        status = run_command(command, cwd=root)
        if status:
            print(f"Quality gate stopped: exit status {status}.", file=sys.stderr)
            return status
    return 0


def _commands(*, full: bool, basetemp_name: str) -> list[Command]:
    python = str(Path(sys.executable))
    commands: list[Command] = [
        (python, "-m", "ruff", "format", "--check", "src", "tests", "scripts"),
        (python, "-m", "ruff", "check", "src", "tests", "scripts"),
        (python, "-m", "mypy"),
    ]
    test_args = ("--basetemp", f".pytest-tmp/{basetemp_name}", "-q")
    if full:
        commands.append(
            (python, "-m", "pytest", "--cov", "--cov-report=term-missing", *test_args)
        )
    else:
        commands.append(
            (python, "-m", "pytest", "tests/unit", "tests/contract", *test_args)
        )
    return commands


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="run the full coverage suite"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="verify that a failing child command produces a nonzero status",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected gate from the repository root."""
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.self_test:
        status = run_command(
            (str(Path(sys.executable)), "-c", "raise SystemExit(17)"), cwd=root
        )
        if status != 17:
            print(f"Failure-path check expected 17, got {status}.", file=sys.stderr)
            return 1
        print("Failure-path check passed.")
        return 0
    name = "t017-full" if args.full else "t017-fast"
    return run_gate(
        _commands(full=args.full, basetemp_name=name), root=root, basetemp_name=name
    )


if __name__ == "__main__":
    raise SystemExit(main())
