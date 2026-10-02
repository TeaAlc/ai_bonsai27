#!/usr/bin/env bash
# Build the opt-in Prism backend for CUDA compute capability 12.0 only.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
source data/logging.sh
bonsai_init_logging blackwell-build
source tools/project.sh
bonsai_step project-lock "Waiting for the checkout lock."
lock_project
revision=f13265492743209a0fbedc2a2781af3f5f0eab13
source_sha=0368b7a5aa02215cafd72b590162ae6b87ca1690be18445c9af7a53145d4c2d5
compiler=docker.io/nvidia/cuda@sha256:4b9ed5fa8361736996499f64ecebf25d4ec37ff56e4d11323ccde10aa36e0c43
jobs=${BONSAI_BUILD_JOBS:-8}
[[ "$jobs" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo 'Error: BONSAI_BUILD_JOBS must be 1–64.' >&2; exit 2; }
# A retained failed build can be resumed without recompiling finished kernels.
resume=false
if (( $# == 0 )); then
    work=$(mktemp -d "$TMPDIR/blackwell-source.XXXXXX")
elif (( $# == 2 )) && [[ "$1" == --resume ]]; then
    resume=true
    work=$(realpath -- "$2")
    temporary_root=$(realpath -- "$TMPDIR")
    [[ "$work" == "$temporary_root/"* && -f "$work/source.tar.gz" && -d "$work/source" ]] \
        || { echo 'Error: resume requires a retained build directory under TMPDIR.' >&2; exit 2; }
else
    echo 'Usage: build-blackwell-backend.sh [--resume <temporary-build-directory>]' >&2
    exit 2
fi
cleanup() {
    local status=$?
    if (( status == 0 )); then
        rm -rf -- "$work"
    else
        bonsai_log ERROR "Build failed; temporary sources and objects retained at $work."
    fi
}
trap cleanup EXIT
if [[ "$resume" == false ]]; then
    bonsai_step source-download "Downloading the pinned Prism source archive."
    curl --fail --location --retry 3 \
        "https://api.github.com/repos/PrismML-Eng/llama.cpp/tarball/$revision" -o "$work/source.tar.gz"
else
    bonsai_step source-download "Resuming retained build: $work"
fi
bonsai_step source-verification "Checking the source SHA256."
printf '%s  %s\n' "$source_sha" "$work/source.tar.gz" | sha256sum --check --status
# Re-extract from the verified archive, removing stray files from a failed run.
# The build directory remains intact so Ninja can reuse completed objects.
rm -rf -- "$work/source"
mkdir -p "$work/source"
tar -xzf "$work/source.tar.gz" --strip-components=1 -C "$work/source"
# GPU injection supplies the real driver for preflight and linker dependency
# resolution. CUDA SDK import stubs are never packaged in the runtime.
# This command compiles only; image creation stays in image_build.sh.
gpu_args=(--device nvidia.com/gpu=all)
if [[ -e /dev/dxg ]]; then
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
fi
# Mount an immutable copy of build scripts. Editing this checkout during a
# long compilation must not change a script while Bash is reading it.
mkdir -p "$work/compiler-tools"
cp tools/compile-blackwell-backend.sh tools/package-blackwell-backend.py tools/check-build-cuda.py "$work/compiler-tools/"
bonsai_step compilation "Compiling native SM120 kernels inside the pinned CUDA image (jobs=$jobs)."
podman run --rm "${gpu_args[@]}" --security-opt label=disable \
    -v "$work:/work:rw" -v "$work/compiler-tools:/tools:ro" \
    -e LD_LIBRARY_PATH=/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64 \
    -e BONSAI_BUILD_JOBS="$jobs" "$compiler" bash /tools/compile-blackwell-backend.sh
bonsai_step runtime-verification "Checking all runtime files and build provenance."
python3 -B tools/verify-blackwell-source.py "$work/runtime"
bonsai_step runtime-publication "Installing the verified runtime under data/backends/blackwell-source."
mkdir -p data/backends/blackwell-source
[[ ! -e data/backends/blackwell-source/runtime.previous ]] \
    || { echo 'Error: resolve the existing Blackwell source runtime.previous first.' >&2; exit 2; }
if [[ -d data/backends/blackwell-source/runtime ]]; then
    mv data/backends/blackwell-source/runtime data/backends/blackwell-source/runtime.previous
fi
if cp -a "$work/runtime" data/backends/blackwell-source/runtime; then
    rm -rf data/backends/blackwell-source/runtime.previous
else
    rm -rf data/backends/blackwell-source/runtime
    [[ ! -d data/backends/blackwell-source/runtime.previous ]] || mv data/backends/blackwell-source/runtime.previous data/backends/blackwell-source/runtime
    exit 2
fi
printf 'Backend prepared. Build the opt-in image with ./image_build.sh --blackwell-source.\n'
