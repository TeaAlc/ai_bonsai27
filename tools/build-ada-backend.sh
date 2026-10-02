#!/usr/bin/env bash
# Build the opt-in Prism backend for CUDA compute capability 8.9 only.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
source tools/project.sh
lock_project
revision=88c4bc60b9c9578f134385be9535e853f2db9b9f
source_sha=cd55b6c23f1ef81c8bd9980ae148b66aeac1bc56b4eaed468b40d2a1247aed7b
compiler=docker.io/nvidia/cuda@sha256:4b9ed5fa8361736996499f64ecebf25d4ec37ff56e4d11323ccde10aa36e0c43
jobs=${BONSAI_BUILD_JOBS:-8}
[[ "$jobs" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo 'Error: BONSAI_BUILD_JOBS must be 1–64.' >&2; exit 2; }
work=$(mktemp -d "$TMPDIR/ada-source.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
curl --fail --location --retry 3 \
    "https://api.github.com/repos/PrismML-Eng/llama.cpp/tarball/$revision" -o "$work/source.tar.gz"
printf '%s  %s\n' "$source_sha" "$work/source.tar.gz" | sha256sum --check --status
mkdir "$work/source"
tar -xzf "$work/source.tar.gz" --strip-components=1 -C "$work/source"
# Actual GPU injection supplies libcuda for linking, never a bundled stub.
# This command compiles only; image creation stays in image_build.sh.
gpu_args=(--device nvidia.com/gpu=all)
if [[ -e /dev/dxg ]]; then
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
fi
podman run --rm "${gpu_args[@]}" --security-opt label=disable \
    -v "$work:/work:rw" -v "$PWD/tools:/tools:ro" \
    -e BONSAI_BUILD_JOBS="$jobs" "$compiler" bash /tools/compile-ada-backend.sh
python3 -B tools/verify-ada-source.py "$work/runtime"
mkdir -p data/backends/ada-source
[[ ! -e data/backends/ada-source/runtime.previous ]] \
    || { echo 'Error: resolve the existing Ada source runtime.previous first.' >&2; exit 2; }
if [[ -d data/backends/ada-source/runtime ]]; then
    mv data/backends/ada-source/runtime data/backends/ada-source/runtime.previous
fi
if cp -a "$work/runtime" data/backends/ada-source/runtime; then
    rm -rf data/backends/ada-source/runtime.previous
else
    rm -rf data/backends/ada-source/runtime
    [[ ! -d data/backends/ada-source/runtime.previous ]] || mv data/backends/ada-source/runtime.previous data/backends/ada-source/runtime
    exit 2
fi
printf 'Backend prepared. Build the opt-in image with ./image_build.sh --ada-source.\n'
