#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_ROOT="$ROOT/runtime-setup"
RUNTIME_ROOT="${ABREX_RUNTIME_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/abrex}"
BOOTSTRAP_PYTHON="${ABREX_BOOTSTRAP_PYTHON:-python3.13}"
CORE_ENV="$RUNTIME_ROOT/venv313"
PLOD_ENV="$RUNTIME_ROOT/plod313"
AB3P_SOURCE="$RUNTIME_ROOT/sources/Ab3P"
NCBI_SOURCE="$RUNTIME_ROOT/sources/NCBITextLib"
AB3P_BUILD="$RUNTIME_ROOT/ab3p-build"
AB3P_MANIFEST="$RUNTIME_ROOT/ab3p-installation-manifest.json"
PLOD_REVISION="019ed5392cad2deab220ad6bfda0681b20cabe21"
PLOD_SHA256="3a72a4130fb589a4191efb5a87a4f3ac1479d48e37649711be6992b2d2b6e277"
PLOD_DIR="$RUNTIME_ROOT/models/plodv2/$PLOD_REVISION"
PLOD_CHECKPOINT="$PLOD_DIR/pytorch_model.bin"
AB3P_COMMIT="41130cddfcba1449ba612905d4a51274f8f565a8"
NCBI_COMMIT="e5ac0d4e0572970911f36099995e4170a12a85e7"

usage() {
  cat <<'EOF'
Usage: ./setup-runtime.sh [--check | --all]

  --check  Check prerequisites and print paths without changing anything.
  --all    Create both Python environments, build Ab3P, download PLOD, and
           write runtime.env. This is the normal fresh-server operation.

Optional environment variables:
  ABREX_RUNTIME_ROOT       Persistent runtime location. Default:
                           ${XDG_DATA_HOME:-$HOME/.local/share}/abrex
  ABREX_BOOTSTRAP_PYTHON   Python 3.13 executable. Default: python3.13

The setup requires network access while it clones sources, installs pinned
packages, and downloads the approximately 394 MB PLOD checkpoint. Runtime jobs
do not need network access.
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "required command not found: $1"
  fi
}

check_python() {
  if ! command -v "$BOOTSTRAP_PYTHON" >/dev/null 2>&1; then
    fail "Python 3.13 was not found as '$BOOTSTRAP_PYTHON'. Load your server's Python 3.13 module or set ABREX_BOOTSTRAP_PYTHON=/absolute/path/to/python3.13, then rerun. uv is not required."
  fi
  "$BOOTSTRAP_PYTHON" -c \
    'import sys; assert sys.version_info[:2] == (3, 13), f"Python 3.13 required, got {sys.version.split()[0]}"' \
    || fail "ABREX_BOOTSTRAP_PYTHON must name Python 3.13"
}

check_prerequisites() {
  check_python
  require_command git
  require_command make
  require_command g++
  require_command curl
  require_command sha256sum
  printf 'Python: %s\n' "$($BOOTSTRAP_PYTHON --version 2>&1)"
  printf 'Runtime root: %s\n' "$RUNTIME_ROOT"
  printf 'All setup prerequisites are available.\n'
}

create_environment() {
  local environment_path="$1"
  local requirements_path="$2"
  shift 2
  if [[ ! -x "$environment_path/bin/python" ]]; then
    printf 'Creating environment: %s\n' "$environment_path"
    "$BOOTSTRAP_PYTHON" -m venv "$environment_path" || fail \
      "unable to create $environment_path; the server's Python may lack the venv/ensurepip component"
  fi
  "$environment_path/bin/python" -c \
    'import sys; assert sys.version_info[:2] == (3, 13)' \
    || fail "existing environment is not Python 3.13: $environment_path"
  printf 'Installing pinned packages into: %s\n' "$environment_path"
  "$environment_path/bin/python" -m pip install "$@" --requirement "$requirements_path"
}

checkout_source() {
  local url="$1"
  local destination="$2"
  local commit="$3"
  if [[ ! -e "$destination" ]]; then
    git clone "$url" "$destination"
  elif [[ ! -d "$destination/.git" ]]; then
    fail "source destination exists but is not a Git checkout: $destination"
  fi
  if [[ -n "$(git -C "$destination" status --porcelain)" ]]; then
    fail "source checkout has local changes; preserve or clean them before retrying: $destination"
  fi
  if ! git -C "$destination" cat-file -e "$commit^{commit}" 2>/dev/null; then
    git -C "$destination" fetch origin "$commit"
  fi
  git -C "$destination" checkout --detach "$commit"
}

setup_ab3p() {
  mkdir -p "$RUNTIME_ROOT/sources"
  checkout_source https://github.com/ncbi-nlp/Ab3P.git \
    "$AB3P_SOURCE" "$AB3P_COMMIT"
  checkout_source https://github.com/ncbi-nlp/NCBITextLib.git \
    "$NCBI_SOURCE" "$NCBI_COMMIT"

  if [[ -f "$AB3P_MANIFEST" && -x "$AB3P_BUILD/Ab3P/identify_abbr_offsets" ]]; then
    printf 'Reusing existing Ab3P installation: %s\n' "$AB3P_BUILD/Ab3P"
    return
  fi
  if [[ -e "$AB3P_BUILD" || -e "$AB3P_MANIFEST" ]]; then
    fail "incomplete Ab3P output already exists. Preserve it for diagnosis, then move it aside and rerun: $AB3P_BUILD or $AB3P_MANIFEST"
  fi
  "$CORE_ENV/bin/python" "$SETUP_ROOT/build_ab3p.py" \
    --ab3p-source "$AB3P_SOURCE" \
    --ncbi-source "$NCBI_SOURCE" \
    --output "$AB3P_BUILD" \
    --manifest "$AB3P_MANIFEST"
}

setup_plod_checkpoint() {
  mkdir -p "$PLOD_DIR"
  if [[ -f "$PLOD_CHECKPOINT" ]]; then
    printf '%s  %s\n' "$PLOD_SHA256" "$PLOD_CHECKPOINT" | sha256sum --check \
      || fail "existing PLOD checkpoint has the wrong checksum: $PLOD_CHECKPOINT"
    printf 'Reusing verified PLOD checkpoint: %s\n' "$PLOD_CHECKPOINT"
    return
  fi
  curl --fail --location --retry 3 --continue-at - \
    --output "$PLOD_CHECKPOINT.part" \
    "https://huggingface.co/surrey-nlp/flair-abbr-pubmed-filtered/resolve/$PLOD_REVISION/pytorch_model.bin"
  printf '%s  %s\n' "$PLOD_SHA256" "$PLOD_CHECKPOINT.part" | sha256sum --check \
    || fail "downloaded PLOD checkpoint failed checksum verification; partial file retained at $PLOD_CHECKPOINT.part"
  mv "$PLOD_CHECKPOINT.part" "$PLOD_CHECKPOINT"
}

write_environment() {
  local environment_file="$ROOT/runtime.env"
  {
    printf '# Generated by setup-runtime.sh; contains paths but no credentials.\n'
    printf 'export ABREX_RUNTIME_ROOT=%q\n' "$RUNTIME_ROOT"
    printf 'export ABREX_CORE_PYTHON=%q\n' "$CORE_ENV/bin/python"
    printf 'export ABREX_PLOD_PYTHON=%q\n' "$PLOD_ENV/bin/python"
    printf 'export ABREX_JOB_DOCTOR_PYTHON=%q\n' "$CORE_ENV/bin/python"
    printf 'export ABREX_AB3P_MANIFEST=%q\n' "$AB3P_MANIFEST"
    printf 'export ABREX_AB3P_ROOT=%q\n' "$AB3P_BUILD/Ab3P"
    printf 'export ABREX_PLODV2_CHECKPOINT=%q\n' "$PLOD_CHECKPOINT"
@@JOB_EXPORTS@@
  } > "$environment_file"
  printf 'Wrote %s\n' "$environment_file"
}

verify_installation() {
  "$CORE_ENV/bin/python" -c 'import pydantic, yaml; print("Core Python dependencies: OK")'
  "$PLOD_ENV/bin/python" -c \
    'import flair, torch; print(f"PLOD dependencies: Flair {flair.__version__}; PyTorch {torch.__version__}")'
  [[ -f "$AB3P_MANIFEST" ]] || fail "Ab3P manifest is missing: $AB3P_MANIFEST"
  [[ -x "$AB3P_BUILD/Ab3P/identify_abbr_offsets" ]] \
    || fail "Ab3P offset executable is missing"
  printf '%s  %s\n' "$PLOD_SHA256" "$PLOD_CHECKPOINT" | sha256sum --check
}

mode="${1:---all}"
case "$mode" in
  --help|-h)
    usage
    ;;
  --check)
    check_prerequisites
    ;;
  --all)
    check_prerequisites
    mkdir -p "$RUNTIME_ROOT"
    create_environment "$CORE_ENV" "$SETUP_ROOT/requirements-core.lock"
    create_environment "$PLOD_ENV" "$SETUP_ROOT/plod-runtime-requirements.txt" \
      --extra-index-url https://download.pytorch.org/whl/cpu
    setup_ab3p
    setup_plod_checkpoint
    write_environment
    verify_installation
    printf '\nSetup complete. Next run:\n  ./doctor.sh\n'
    ;;
  *)
    usage >&2
    fail "unknown option: $mode"
    ;;
esac
