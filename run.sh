#!/usr/bin/env bash
set -euo pipefail
# The writable cache holds downloaded models across container restarts.
# Resolve relative paths against the caller's directory before changing directories.
model_dir=${BONSAI_MODEL_DIR:-"$PWD"}
mkdir -p -- "$model_dir"
model_dir=$(cd -- "$model_dir" && pwd)
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Context size must be an integer >= 512. Reasoning values accepted by the
# official Bonsai 2 chat template: low, medium, xhigh. xhigh is the model
# default; medium gives shorter reasoning. low is accepted but may behave
# much like xhigh. high is not accepted by this model.
ctx_size=${BONSAI_CTX_SIZE:-16384}
reasoning_effort=${BONSAI_REASONING_EFFORT:-medium}
# latest points to the last successful local build; use a versioned tag to pin it.
image=${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}
source data/gpu/settings.sh
validate_bonsai_settings
validate_decimal BONSAI_PORT "${BONSAI_PORT:-8080}" 1 65535
ctx_size=$((10#$ctx_size))
port=$((10#${BONSAI_PORT:-8080}))

# WSL2 provides CUDA through /dev/dxg and Windows driver libraries;
# native Linux uses the already configured NVIDIA CDI device.
if [[ -e /dev/dxg ]]; then
    [[ -d /usr/lib/wsl/lib ]] || { echo 'Error: WSL driver directory is missing.' >&2; exit 2; }
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
else
    gpu_args=(--device nvidia.com/gpu=all)
fi
# Detection runs inside the container against its actual CUDA device 0.
# An explicit override is checked against that device before any downloads.
# Publish only on localhost and mount the persistent model cache. Arguments after
# the image name are forwarded to the container's llama-server entrypoint.
exec podman run \
    -d \
    --name "${BONSAI_CONTAINER_NAME:-bonsai2-27b}" \
    "${gpu_args[@]}" \
    -p "127.0.0.1:$port:8080" \
    -v "$model_dir:/models:rw" \
    -e "BONSAI_CTX_SIZE=$ctx_size" \
    -e "BONSAI_GPU_BACKEND=${BONSAI_GPU_BACKEND:-}" \
    -e "BONSAI_REASONING_EFFORT=$reasoning_effort" \
    -e "BONSAI_DOWNLOAD_WAIT_SECONDS=${BONSAI_DOWNLOAD_WAIT_SECONDS:-600}" \
    -e "BONSAI_DOWNLOAD_TIMEOUT=${BONSAI_DOWNLOAD_TIMEOUT:-3600}" \
    --security-opt label=disable \
    "$image" \
    "$@"
