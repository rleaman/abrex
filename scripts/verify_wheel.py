"""Build and smoke-test the wheel in a disposable environment without network."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from quality_gate import development_python

Command = tuple[str, ...]


def _run(
    command: Command,
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def _source_environment(root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    return environment


def _wheel_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def _venv_python(environment_root: Path) -> Path:
    relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return environment_root / relative


def _capture(command: Command, *, cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _installed_smoke(root: Path, work: Path, expected_prefix: Path) -> None:
    import abrex
    from abrex.domain import Document
    from abrex.experiments import run_experiment
    from abrex.resolvers import SchwartzHearstResolver
    from abrex.resources import FrequencyResourceConfig, import_frequency_resource

    if abrex.__file__ is None:
        raise RuntimeError("wheel package has no importable package file")
    origin = Path(abrex.__file__).resolve()
    source = (root / "src").resolve()
    if origin.is_relative_to(source) or not origin.is_relative_to(expected_prefix):
        raise RuntimeError(
            f"expected wheel import below {expected_prefix}, imported {origin}"
        )

    document = Document("wheel-smoke", "Tumor necrosis factor (TNF) is measured.")
    predictions = tuple(SchwartzHearstResolver().resolve(document))
    if len(predictions) != 1 or predictions[0].short_form_text != "TNF":
        raise RuntimeError("local document resolution smoke produced an invalid result")

    experiment_config = work / "offline-experiment.yaml"
    experiment_config.write_text(
        json.dumps(
            {
                "project": {"name": "wheel-smoke", "seed": 20260908},
                "corpus": {
                    "type": "canonical_jsonl",
                    "params": {
                        "path": str(root / "docs/examples/experiment-corpus.jsonl"),
                        "manifest_path": str(
                            root / "docs/examples/experiment-corpus.manifest.json"
                        ),
                    },
                },
                "resolver": {"type": "toy", "params": {"confidence": 1.0}},
                "matching": {"type": "exact_pair", "params": {}},
                "metrics": [
                    {
                        "type": "pair_prf",
                        "params": {"averaging": "micro", "zero_division": "zero"},
                    }
                ],
                "reporters": [{"type": "json", "params": {}}],
                "output": {"root": str(work / "experiment-output")},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    experiment = run_experiment((experiment_config,))
    if not experiment.manifest_path.is_file() or not experiment.report_paths:
        raise RuntimeError("offline experiment smoke did not write expected artifacts")

    resource_source = work / "resource.json.gz"
    with gzip.open(resource_source, "wt", encoding="utf-8") as stream:
        json.dump({"TNF": {"tumor necrosis factor": 2}}, stream)
    resource = import_frequency_resource(
        FrequencyResourceConfig(
            source_path=resource_source,
            sqlite_path=work / "resource.sqlite",
        )
    )
    variants = resource.lookup("TNF")
    if len(variants) != 1 or variants[0].count != 2:
        raise RuntimeError("local SQLite resource query returned an invalid result")

    print(
        json.dumps(
            {
                "document_predictions": len(predictions),
                "experiment_manifest": str(experiment.manifest_path),
                "package_origin": str(origin),
                "resource_variants": len(variants),
            },
            sort_keys=True,
        )
    )


def verify_wheel(root: Path, work_parent: Path | None = None) -> None:
    """Build, install, smoke-test, and discard one isolated wheel environment."""
    root = root.resolve()
    if work_parent is not None:
        work_parent.mkdir(parents=True, exist_ok=True)
    development = development_python(root)
    source_environment = _source_environment(root)
    clean_environment = _wheel_environment()
    verifier = root / "scripts" / "verify_source_import.py"
    _run(
        (str(development), str(verifier), "--root", str(root)),
        cwd=root,
        environment=source_environment,
    )
    with tempfile.TemporaryDirectory(
        prefix="abrex-wheel-smoke-",
        dir=work_parent,
    ) as temporary:
        work = Path(temporary)
        wheel_directory = work / "wheel"
        wheel_directory.mkdir()
        _run(
            (
                str(development),
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                ".",
                "--wheel-dir",
                str(wheel_directory),
            ),
            cwd=root,
            environment=clean_environment,
        )
        wheels = tuple(wheel_directory.glob("abrex-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one abrex wheel, found {len(wheels)}")

        environment_root = work / "venv"
        _run(
            (str(development), "-m", "venv", str(environment_root)),
            cwd=work,
            environment=clean_environment,
        )
        python = _venv_python(environment_root)
        development_site = _capture(
            (
                str(development),
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ),
            cwd=root,
        )
        wheel_site = Path(
            _capture(
                (
                    str(python),
                    "-c",
                    "import sysconfig; print(sysconfig.get_path('purelib'))",
                ),
                cwd=work,
            )
        )
        (wheel_site / "abrex-smoke-dependencies.pth").write_text(
            development_site + "\n", encoding="utf-8", newline="\n"
        )
        _run(
            (
                str(python),
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "--no-deps",
                str(wheels[0]),
            ),
            cwd=work,
            environment=clean_environment,
        )
        _run(
            (
                str(python),
                str(Path(__file__).resolve()),
                "--installed-smoke",
                "--root",
                str(root),
                "--work",
                str(work),
                "--expected-prefix",
                str(wheel_site),
            ),
            cwd=work,
            environment=clean_environment,
        )

    _run(
        (str(development), str(verifier), "--root", str(root)),
        cwd=root,
        environment=source_environment,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument(
        "--installed-smoke", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument("--work", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--expected-prefix", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the outer verifier or the installed-package smoke phase."""
    args = _parser().parse_args(argv)
    if args.installed_smoke:
        if args.work is None or args.expected_prefix is None:
            raise SystemExit("--work and --expected-prefix are required")
        _installed_smoke(args.root.resolve(), args.work, args.expected_prefix.resolve())
    else:
        verify_wheel(args.root, args.work_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
