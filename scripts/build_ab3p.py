"""Build and verify the supplied upstream Ab3P sources inside Linux/WSL.

The script deliberately keeps the upstream detector and Makefiles intact. It
copies both source trees into a task-owned output directory, applies only the
documented CRLF and modern-GCC compatibility repairs, builds with the
upstream make targets, runs the upstream comparison, and writes a
path-independent installation manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

RESOURCE_TEXT_FILES = (
    Path("WordData/Ab3P_prec.dat"),
    Path("WordData/Lf1chSf"),
    Path("WordData/SingTermFreq.dat"),
    Path("WordData/stop"),
)
SEMANTIC_RESOURCE_FILES = (
    Path("WordData/Ab3P_prec.dat"),
    Path("WordData/Lf1chSf"),
    Path("WordData/SingTermFreq.dat"),
    Path("WordData/stop"),
    Path("WordData/cshset_wrdset3.ad"),
    Path("WordData/cshset_wrdset3.ct"),
    Path("WordData/cshset_wrdset3.ha"),
    Path("WordData/cshset_wrdset3.nm"),
    Path("WordData/cshset_wrdset3.str"),
    Path("WordData/hshset_Lf1chSf.ad"),
    Path("WordData/hshset_Lf1chSf.ha"),
    Path("WordData/hshset_Lf1chSf.nm"),
    Path("WordData/hshset_Lf1chSf.str"),
    Path("WordData/hshset_stop.ad"),
    Path("WordData/hshset_stop.ha"),
    Path("WordData/hshset_stop.nm"),
    Path("WordData/hshset_stop.str"),
)


def sha256_file(path: Path) -> str:
    """Hash a file without loading large resources into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root: Path) -> str:
    """Return a deterministic digest of a source tree, excluding ``.git``."""

    digest = hashlib.sha256()
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def _git_value(root: Path, expression: str) -> str | None:
    """Read a Git identity when the supplied source includes Git metadata."""

    if not (root / ".git").exists():
        return None
    command = [
        "git",
        "-c",
        f"safe.directory={root}",
        "-C",
        os.fspath(root),
        "rev-parse",
        expression,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _source_identity(root: Path) -> dict[str, str | None]:
    return {
        "git_commit": _git_value(root, "HEAD"),
        "git_tree": _git_value(root, "HEAD^{tree}"),
        "source_tree_sha256": tree_digest(root),
    }


def _normalize_line_endings(root: Path) -> list[str]:
    changed: list[str] = []
    path_file = root / "path_Ab3P"
    targets = (path_file, *tuple(root / relative for relative in RESOURCE_TEXT_FILES))
    for path in targets:
        data = path.read_bytes()
        normalized = data.replace(b"\r\n", b"\n")
        if normalized != data:
            path.write_bytes(normalized)
            changed.append(path.relative_to(root).as_posix())
    return changed


def _patch_modern_gcc_header(root: Path) -> str:
    path = root / "lib/AbbrvE.h"
    text = path.read_text(encoding="utf-8")
    old = "bool rate( int i ) const { my_rate[i]; }"
    new = "bool rate( int i ) const { return my_rate[i]; }"
    if old not in text:
        if new in text:
            return path.relative_to(root).as_posix() + " (already patched)"
        raise RuntimeError(f"Expected compatibility target is absent: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    return path.relative_to(root).as_posix()


def _run(
    command: list[str],
    cwd: Path,
    *,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    rendered = " ".join(command)
    print(f"+ (cd {cwd} && {rendered})")
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=env,
    )


def _version(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()[0].strip()


def _artifact(root: Path, relative: Path, *, role: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise RuntimeError(f"Expected build artifact is missing: {path}")
    return {
        "path": relative.as_posix(),
        "role": role,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _write_run_output(path: Path, result: subprocess.CompletedProcess[str]) -> None:
    path.write_text(result.stdout, encoding="utf-8", newline="\n")
    if result.stderr:
        path.with_suffix(".stderr.txt").write_text(
            result.stderr, encoding="utf-8", newline="\n"
        )


def _definition_count(output: str) -> int:
    return sum(
        1
        for line in output.splitlines()
        if line.startswith("  ") and line.count("|") >= 2
    )


def _offset_record_count(output: str) -> int:
    return sum(1 for line in output.splitlines() if line.strip())


def build(args: argparse.Namespace) -> dict[str, Any]:
    if os.name != "posix":
        raise RuntimeError(
            "Run this builder inside Linux/WSL; it does not create a Windows binary"
        )

    ab3p_source = Path(args.ab3p_source).resolve()
    ncbi_source = Path(args.ncbi_source).resolve()
    output = Path(args.output).resolve()
    manifest_path = Path(args.manifest).resolve()
    if not ab3p_source.is_dir() or not ncbi_source.is_dir():
        raise FileNotFoundError(
            "Both --ab3p-source and --ncbi-source must be directories"
        )
    if output.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing build directory: {output}"
        )

    source_identities = {
        "Ab3P": _source_identity(ab3p_source),
        "NCBITextLib": _source_identity(ncbi_source),
    }
    output.mkdir(parents=True)
    ab3p_root = output / "Ab3P"
    # The upstream library Makefile is entered from Ab3P/lib but reuses the
    # top-level NCBITEXTLIB value. Keep a sibling source copy plus a relative
    # symlink under Ab3P so ../NCBITextLib is valid from both make directories.
    ncbi_root = output / "NCBITextLib"
    shutil.copytree(ab3p_source, ab3p_root)
    shutil.copytree(ncbi_source, ncbi_root)
    (ab3p_root / "NCBITextLib").symlink_to(
        Path("..") / "NCBITextLib", target_is_directory=True
    )

    normalized_files = _normalize_line_endings(ab3p_root)
    gcc_patch = _patch_modern_gcc_header(ab3p_root)
    prepared_identities = {
        "Ab3P": tree_digest(ab3p_root),
        "NCBITextLib": tree_digest(ncbi_root),
    }

    compiler = shutil.which("g++")
    if compiler is None:
        raise RuntimeError("g++ is required; run the builder inside Linux/WSL")
    tool_dir = output / "build-tools"
    tool_dir.mkdir()
    compiler_wrapper = tool_dir / "g++"
    compiler_wrapper.write_text(
        "#!/bin/sh\n"
        f"exec {shlex.quote(compiler)} "
        f'-fdebug-prefix-map={shlex.quote(output.as_posix())}=/ab3p-build "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    compiler_wrapper.chmod(0o755)
    build_env = os.environ.copy()
    build_env["PATH"] = f"{tool_dir}{os.pathsep}{build_env['PATH']}"

    _run(["make"], ncbi_root / "lib", env=build_env)
    _run(
        ["make", "NCBITEXTLIB=../NCBITextLib", "all"],
        ab3p_root,
        env=build_env,
    )
    offset_frontend_source = Path(__file__).with_name("ab3p_offset_frontend.C")
    if not offset_frontend_source.is_file():
        raise FileNotFoundError(
            f"Missing offset frontend source: {offset_frontend_source}"
        )
    offset_frontend = ab3p_root / "identify_abbr_offsets"
    _run(
        [
            os.fspath(compiler_wrapper),
            "-std=c++11",
            "-g",
            "-I",
            os.fspath(ab3p_root / "lib"),
            "-I",
            os.fspath(ncbi_root / "include"),
            os.fspath(offset_frontend_source),
            "-L",
            os.fspath(ab3p_root / "lib"),
            "-lAb3P",
            "-L",
            os.fspath(ncbi_root / "lib"),
            "-lText",
            "-o",
            os.fspath(offset_frontend),
        ],
        output,
        env=build_env,
    )
    upstream = _run(["make", "test"], ab3p_root, capture=True)

    verification = output / "verification"
    verification.mkdir()
    smoke_input = verification / "nonascii-multiline.input.txt"
    smoke_input.write_text(
        "Café study of tumor necrosis factor (TNF).\n"
        "第二行: interleukin 6 (IL-6) is measured.\n"
        "β blocker (BB) remains under review.\n",
        encoding="utf-8",
        newline="\n",
    )
    executable = ab3p_root / "identify_abbr"
    smoke = _run(
        [os.fspath(executable), os.fspath(smoke_input)], ab3p_root, capture=True
    )
    _write_run_output(verification / "nonascii-multiline.stdout.txt", smoke)
    offset_smoke = _run(
        [os.fspath(offset_frontend), os.fspath(smoke_input)],
        ab3p_root,
        capture=True,
    )
    _write_run_output(verification / "nonascii-multiline.offsets.jsonl", offset_smoke)

    other_cwd = verification / "other-working-directory"
    other_cwd.mkdir()
    (other_cwd / "path_Ab3P").write_text(
        f"{(ab3p_root / 'WordData').as_posix()}/\n",
        encoding="utf-8",
        newline="\n",
    )
    other = _run(
        [os.fspath(executable), os.fspath(smoke_input)], other_cwd, capture=True
    )
    _write_run_output(verification / "other-working-directory.stdout.txt", other)

    missing_cwd = verification / "missing-resource"
    missing_cwd.mkdir()
    (missing_cwd / "path_Ab3P").write_text(
        f"{(output / 'missing-WordData').as_posix()}/\n",
        encoding="utf-8",
        newline="\n",
    )
    missing = subprocess.run(
        [os.fspath(executable), os.fspath(smoke_input)],
        cwd=missing_cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    (verification / "missing-resource.stdout.txt").write_text(
        missing.stdout + missing.stderr, encoding="utf-8", newline="\n"
    )
    if missing.returncode == 0:
        raise RuntimeError("Missing-resource smoke unexpectedly succeeded")

    resources = [
        _artifact(ab3p_root, relative, role="semantic-resource")
        for relative in SEMANTIC_RESOURCE_FILES
    ]
    artifacts = [
        _artifact(ab3p_root, Path("identify_abbr"), role="executable"),
        _artifact(ab3p_root, Path("identify_abbr_offsets"), role="executable"),
        _artifact(ab3p_root, Path("lib/libAb3P.a"), role="static-library"),
        _artifact(ncbi_root, Path("lib/libText.a"), role="static-library"),
        *resources,
    ]
    manifest: dict[str, Any] = {
        "schema_version": "ab3p-installation-v1",
        "installation": {
            "name": "NLM Ab3P supplied source build",
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "compiler": _version([compiler, "--version"]),
            "make": _version(["make", "--version"]),
            "build_flags": {
                "Ab3P": "-g",
                "NCBITextLib": "-std=c++11 -gdwarf-2",
                "debug_prefix_map": "/ab3p-build",
            },
            "make_commands": [
                {"cwd": "NCBITextLib/lib", "argv": ["make"]},
                {
                    "cwd": "Ab3P",
                    "argv": ["make", "NCBITEXTLIB=../NCBITextLib", "all"],
                },
            ],
        },
        "sources": source_identities,
        "prepared_source_tree_sha256": prepared_identities,
        "compatibility_repairs": {
            "line_endings": normalized_files,
            "modern_gcc": [gcc_patch],
        },
        "artifacts": artifacts,
        "verification": {
            "upstream_make_test": {
                "command": ["make", "test"],
                "status": "passed",
                "exit_status": upstream.returncode,
            },
            "nonascii_multiline_smoke": {
                "input": "verification/nonascii-multiline.input.txt",
                "stdout": "verification/nonascii-multiline.stdout.txt",
                "definition_count": _definition_count(smoke.stdout),
                "exit_status": smoke.returncode,
            },
            "nonascii_multiline_offset_smoke": {
                "input": "verification/nonascii-multiline.input.txt",
                "stdout": "verification/nonascii-multiline.offsets.jsonl",
                "record_count": _offset_record_count(offset_smoke.stdout),
                "exit_status": offset_smoke.returncode,
            },
            "other_working_directory": {
                "path_file": "verification/other-working-directory/path_Ab3P",
                "stdout": "verification/other-working-directory.stdout.txt",
                "status": "passed",
                "exit_status": other.returncode,
            },
            "missing_resource": {
                "stdout": "verification/missing-resource.stdout.txt",
                "status": "failed-as-expected",
                "exit_status": missing.returncode,
            },
        },
        "notices": [
            "Ab3P/README.md: Public Domain Notice",
            "NCBITextLib/README.md: Public Domain Notice",
        ],
        "windows_execution": {
            "supported_path": "wsl.exe -d Ubuntu -- Linux command path",
            "native_windows_binary": False,
            "cache_export": (
                "Copy raw ABREX cache files from the Linux checkout for Windows "
                "cache_only replay."
            ),
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote installation manifest: {manifest_path}")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ab3p-source", default="../Ab3P", type=Path)
    parser.add_argument("--ncbi-source", default="../NCBITextLib", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        build(parse_args(argv))
    except (
        FileExistsError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Ab3P build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
