"""Run the repository's fail-fast, offline quality gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Sequence
from pathlib import Path

Command = tuple[str, ...]


def development_python(root: Path, requested: Path | None = None) -> Path:
    """Return the interpreter that owns this checkout's development tools."""
    if requested is not None:
        return requested.absolute()
    # Resolving a venv's executable symlink selects the base interpreter and
    # loses the environment's installed tools on POSIX.
    current = Path(sys.executable).absolute()
    candidates = (
        root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
        root / "env313" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
    )
    if current in (
        candidate.absolute() for candidate in candidates if candidate.is_file()
    ):
        return current
    for candidate in candidates:
        if candidate.is_file():
            return candidate.absolute()
    return current


def run_command(command: Command, *, cwd: Path) -> int:
    """Run one command and return its exact exit status."""
    print(f"+ {' '.join(command)}", flush=True)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(cwd / "src")
    result = subprocess.run(command, cwd=cwd, check=False, env=environment)
    return result.returncode


def run_gate(commands: Sequence[Command], *, root: Path) -> int:
    """Run commands in order and stop at the first failed command."""
    for command in commands:
        status = run_command(command, cwd=root)
        if status:
            print(f"Quality gate stopped: exit status {status}.", file=sys.stderr)
            return status
    return 0


def unique_pytest_basetemp(*, full: bool) -> Path:
    """Return a collision-free system-temporary directory for one gate run."""

    gate = "full" if full else "fast"
    return Path(tempfile.gettempdir()) / (
        f"abrex-quality-{gate}-{os.getpid()}-{uuid.uuid4().hex}"
    )


def _commands(*, root: Path, python: Path, full: bool, basetemp: Path) -> list[Command]:
    executable = str(python)
    commands: list[Command] = [
        (
            executable,
            str(Path("scripts") / "verify_source_import.py"),
            "--root",
            str(root),
        ),
        (executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts"),
        (executable, "-m", "ruff", "check", "src", "tests", "scripts"),
        (executable, "-m", "mypy"),
    ]
    # Python 3.13's Windows 0o700 ACL handling also affects pytest's cache
    # atomic-write temporary directories under managed process tokens. The
    # cache is not evidence and is unnecessary in the reproducibility gate.
    test_args = (
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(basetemp),
        "-q",
    )
    if full:
        commands.append(
            (
                executable,
                "-m",
                "pytest",
                "--cov",
                "--cov-report=term-missing",
                *test_args,
            )
        )
    else:
        commands.append(
            (
                executable,
                "-m",
                "pytest",
                "tests/unit",
                "tests/contract",
                *test_args,
            )
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
    parser.add_argument(
        "--python",
        type=Path,
        help="development interpreter override (defaults to .venv/env313 when present)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected gate from the repository root."""
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    python = development_python(root, args.python)
    print(f"launcher python is {Path(sys.executable).absolute()}")
    print(f"gate python is {python}")
    if args.self_test:
        status = run_command((str(python), "-c", "raise SystemExit(17)"), cwd=root)
        if status != 17:
            print(f"Failure-path check expected 17, got {status}.", file=sys.stderr)
            return 1
        print("Failure-path check passed.")
        return 0
    return run_gate(
        _commands(
            root=root,
            python=python,
            full=args.full,
            basetemp=unique_pytest_basetemp(full=args.full),
        ),
        root=root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
