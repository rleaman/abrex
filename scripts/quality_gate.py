"""Run the repository's fail-fast, offline quality gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

Command = tuple[str, ...]


def development_python(root: Path, requested: Path | None = None) -> Path:
    """Return the interpreter that owns this checkout's development tools."""
    if requested is not None:
        return requested.resolve()
    current = Path(sys.executable).resolve()
    candidates = (
        root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
        root / "env313" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
    )
    if current in (
        candidate.resolve() for candidate in candidates if candidate.is_file()
    ):
        return current
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return current


def run_command(command: Command, *, cwd: Path) -> int:
    """Run one command and return its exact exit status."""
    print(f"+ {' '.join(command)}", flush=True)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(cwd / "src")
    result = subprocess.run(command, cwd=cwd, check=False, env=environment)
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


def _commands(
    *, root: Path, python: Path, full: bool, basetemp_name: str
) -> list[Command]:
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
    test_args = ("--basetemp", f".pytest-tmp/{basetemp_name}", "-q")
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
    print(f"launcher python is {Path(sys.executable).resolve()}")
    print(f"gate python is {python}")
    if args.self_test:
        status = run_command((str(python), "-c", "raise SystemExit(17)"), cwd=root)
        if status != 17:
            print(f"Failure-path check expected 17, got {status}.", file=sys.stderr)
            return 1
        print("Failure-path check passed.")
        return 0
    name = "t017-full" if args.full else "t017-fast"
    return run_gate(
        _commands(
            root=root,
            python=python,
            full=args.full,
            basetemp_name=name,
        ),
        root=root,
        basetemp_name=name,
    )


if __name__ == "__main__":
    raise SystemExit(main())
