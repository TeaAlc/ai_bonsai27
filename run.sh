#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/data/logging.sh"
bonsai_init_logging run
bonsai_step configuration "Reading options and validating prerequisites."
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

bonsai_step image-selection "Checking the local image: $image"
# Ask before downloading; an empty answer accepts the public project image.
# Exit on engine errors or closed stdin rather than silently downloading.
if podman image exists "$image"; then
    bonsai_log INFO "Using the locally available image: $image"
else
    image_status=$?
    if [[ "$image_status" != 1 ]]; then
        bonsai_log ERROR "Cannot check local images (exit=$image_status). Check the Podman engine connection."
        exit "$image_status"
    fi
    remote_default=ghcr.io/teaalc/ai_bonsai27:latest
    printf 'Local image %s is missing.\nRemote image to download [%s]: ' "$image" "$remote_default" >&2
    if ! IFS= read -r remote_image; then
        bonsai_log ERROR "No download address confirmed. Enter an image reference or press Enter to accept the default."
        exit 2
    fi
    image=${remote_image:-$remote_default}
    if [[ "$image" == -* || "$image" == *[[:space:]]* ]]; then
        bonsai_log ERROR "The image reference must not start with '-' or contain whitespace."
        exit 2
    fi
    bonsai_step image-download "Pulling the confirmed image: $image"
    podman pull "$image"
fi

bonsai_step gpu-routing "Choosing host GPU access for the container."
# WSL2 provides CUDA through /dev/dxg and Windows driver libraries;
# native Linux uses the already configured NVIDIA CDI device.
if [[ -e /dev/dxg ]]; then
    [[ -d /usr/lib/wsl/lib ]] || { echo 'Error: WSL driver directory is missing.' >&2; exit 2; }
    bonsai_log INFO "Using WSL /dev/dxg and read-only /usr/lib/wsl driver mount."
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
else
    bonsai_log INFO "Using NVIDIA CDI; the selected engine must already have a GPU specification."
    gpu_args=(--device nvidia.com/gpu=all)
fi
# Detection runs inside the container against its actual CUDA device 0.
# An explicit override is checked against that device before any downloads.
# Publish only on localhost and mount the persistent model cache. Arguments after
# the image name are forwarded to the container's llama-server entrypoint.
bonsai_step container-create "Creating ${BONSAI_CONTAINER_NAME:-bonsai2-27b}: image=$image; cache=$model_dir; endpoint=http://127.0.0.1:$port; context=$ctx_size; reasoning=$reasoning_effort."
podman run \
    -d \
    --pull=never \
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

bonsai_log INFO "Container created. Follow startup with: podman logs -f ${BONSAI_CONTAINER_NAME:-bonsai2-27b}"
