#!/usr/bin/env bash
set -euo pipefail
image=${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}
mkdir -p /tmp/bonsai27
work_dir=$(mktemp -d /tmp/bonsai27/runtime-test.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT

# Check both packaged backends with the host's real CUDA driver attached.
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
if podman run --rm -e NVIDIA_VISIBLE_DEVICES=void -e BONSAI_GPU_BACKEND=blackwell \
    -v "$work_dir/models:/models:rw" --security-opt label=disable \
    "$image" > "$work_dir/no-gpu.log" 2>&1; then
    echo 'Error: startup succeeded without GPU access.' >&2
    exit 1
fi
if [[ $(< "$work_dir/no-gpu.log") != *'CUDA driver/GPU access is unavailable'* ]]; then
    cat "$work_dir/no-gpu.log" >&2
    exit 1
fi
[[ -z $(ls -A "$work_dir/models") ]]
echo 'Passed both backend dependency checks and pre-download CUDA failure check.'
