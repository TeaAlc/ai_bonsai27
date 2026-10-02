#!/usr/bin/env bash
# Prepare one allowlisted native backend; image creation stays separate.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
profile=${1:?Expected ada or blackwell}
shift
case "$profile" in ada|blackwell) ;; *) echo 'Error: unknown backend profile.' >&2; exit 2 ;; esac
source data/logging.sh
bonsai_init_logging "$profile-build"
source tools/project.sh
bonsai_step project-lock "Waiting for the checkout lock."
lock_project
# Snapshot every consumed compiler helper before reading profile inputs.
profile_snapshot=$(mktemp -d "$TMPDIR/backend-tools.XXXXXX")
cp tools/compile-backend.sh tools/package-backend.py tools/backend_profile.py tools/backend-profiles.json tools/check-build-cuda.py tools/verify-source.py tools/verify-backend.py "$profile_snapshot/"
trap 'rm -rf -- "$profile_snapshot"' EXIT
# Load fixed inputs from the shared, allowlisted profile.
revision=$(python3 -B "$profile_snapshot/backend_profile.py" "$profile" source_revision)
source_sha=$(python3 -B "$profile_snapshot/backend_profile.py" "$profile" source_sha256)
compiler=$(python3 -B "$profile_snapshot/backend_profile.py" "$profile" compiler_image)
jobs=${BONSAI_BUILD_JOBS:-8}
[[ "$jobs" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo 'Error: BONSAI_BUILD_JOBS must be 1–64.' >&2; exit 2; }
# A retained failed build can be resumed without recompiling finished kernels.
resume=false
if (( $# == 0 )); then
    work=$(mktemp -d "$TMPDIR/$profile-source.XXXXXX")
elif [[ "$profile" == blackwell ]] && (( $# == 2 )) && [[ "$1" == --resume ]]; then
    resume=true
    work=$(realpath -- "$2")
    temporary_root=$(realpath -- "$TMPDIR")
    [[ "$work" == "$temporary_root/"* && -f "$work/source.tar.gz" && -d "$work/source" ]] \
        || { echo 'Error: resume requires a retained build directory under TMPDIR.' >&2; exit 2; }
else
    if [[ "$profile" == blackwell ]]; then
        echo 'Usage: build-blackwell-backend.sh [--resume <temporary-build-directory>]' >&2
    else
        echo 'Usage: build-ada-backend.sh' >&2
    fi
    exit 2
fi
cleanup() {
    local status=$?
    rm -rf -- "$profile_snapshot"
    if (( status == 0 )) || [[ "$profile" == ada ]]; then
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
cp "$profile_snapshot/"* "$work/compiler-tools/"
bonsai_step compilation "Compiling native $profile kernels inside the pinned CUDA image (jobs=$jobs)."
podman run --rm "${gpu_args[@]}" --security-opt label=disable \
    -v "$work:/work:rw" -v "$work/compiler-tools:/tools:ro" \
    -e LD_LIBRARY_PATH=/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64 \
    -e BONSAI_BUILD_JOBS="$jobs" "$compiler" bash /tools/compile-backend.sh "$profile"
bonsai_step runtime-verification "Checking all runtime files and build provenance."
python3 -B "$work/compiler-tools/verify-source.py" "$work/runtime" "$profile"
# Keep the previous runtime until the replacement has been copied successfully.
# Image preparation can recover runtime.previous after an interrupted install.
backend_root="data/backends/$profile-source"
runtime="$backend_root/runtime"
bonsai_step runtime-publication "Installing the verified runtime under $backend_root."
mkdir -p "$backend_root"
[[ ! -e "$runtime.previous" ]] \
    || { echo "Error: resolve the existing $profile source runtime.previous first." >&2; exit 2; }
if [[ -d "$runtime" ]]; then
    mv -- "$runtime" "$runtime.previous"
fi
if cp -a "$work/runtime" "$runtime"; then
    rm -rf -- "$runtime.previous"
else
    rm -rf -- "$runtime"
    [[ ! -d "$runtime.previous" ]] || mv -- "$runtime.previous" "$runtime"
    exit 2
fi
printf 'Backend prepared. Build the image with ./image_build.sh --%s-source.\n' "$profile"
