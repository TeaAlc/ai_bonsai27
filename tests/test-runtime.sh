#!/usr/bin/env bash
set -euo pipefail
image=${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}
mkdir -p /tmp/bonsai27
work_dir=$(mktemp -d /tmp/bonsai27/runtime-test.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT

# Check all packaged backends with the host's real CUDA driver attached.
if [[ -e /dev/dxg ]]; then
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
else
    gpu_args=(--device nvidia.com/gpu=all)
fi
podman run --rm "${gpu_args[@]}" --entrypoint bash "$image" \
    /opt/bonsai/check-runtime.sh

# A backend override must not hide missing driver access or trigger downloads.
# Disable NVIDIA visibility so a globally configured runtime cannot inject a GPU.
mkdir "$work_dir/models"
for backend in auto blackwell ampere-ada; do
    backend_args=()
    [[ "$backend" == auto ]] || backend_args=(-e "BONSAI_GPU_BACKEND=$backend")
    if podman run --rm -e NVIDIA_VISIBLE_DEVICES=void "${backend_args[@]}" \
        -v "$work_dir/models:/models:rw" --security-opt label=disable \
        "$image" > "$work_dir/no-gpu-$backend.log" 2>&1; then
        echo 'Error: startup succeeded without GPU access.' >&2
        exit 1
    fi
    logs=$(< "$work_dir/no-gpu-$backend.log")
    [[ "$logs" == *'[gpu-access] [ERROR]'* && "$logs" == *'BONSAI_GPU_BACKEND cannot provide GPU access'* ]]
    [[ "$logs" != *'or set BONSAI_GPU_BACKEND explicitly'* && "$logs" != *'Downloading missing'* ]]
    [[ -z $(ls -A "$work_dir/models") ]]
done
# Validation and cache failures must be reported before the GPU stage.
if podman run --rm -e BONSAI_CTX_SIZE=invalid "$image" > "$work_dir/settings.log" 2>&1; then exit 1; fi
[[ $(< "$work_dir/settings.log") == *'[configuration]'* ]]
[[ $(< "$work_dir/settings.log") != *'[gpu-access]'* ]]
if podman run --rm -v "$work_dir/models:/models:ro" "$image" > "$work_dir/cache.log" 2>&1; then exit 1; fi
[[ $(< "$work_dir/cache.log") == *'[model-cache] [ERROR]'* ]]
[[ $(< "$work_dir/cache.log") != *'[gpu-access]'* ]]
echo 'Passed packaged backend dependency checks and pre-download CUDA failure check.'
