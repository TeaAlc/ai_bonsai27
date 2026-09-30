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
if [[ ! "$ctx_size" =~ ^[0-9]+$ ]] || (( 10#$ctx_size < 512 )); then
    echo 'BONSAI_CTX_SIZE must be an integer of at least 512' >&2
    exit 2
fi
case "$reasoning_effort" in
    low|medium|xhigh) ;;
    *)
        echo 'BONSAI_REASONING_EFFORT must be low, medium, or xhigh' >&2
        exit 2
        ;;
esac

# WSL2 provides CUDA through /dev/dxg and Windows driver libraries;
# native Linux uses the already configured NVIDIA CDI device.
if [[ -e /dev/dxg ]]; then
    if [[ ! -x /usr/lib/wsl/lib/nvidia-smi ]]; then
        echo 'WSL NVIDIA driver is missing' >&2
        exit 2
    fi
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
    smi=/usr/lib/wsl/lib/nvidia-smi
else
    gpu_args=(--device nvidia.com/gpu=all)
    if ! smi=$(command -v nvidia-smi); then
        echo 'NVIDIA driver/nvidia-smi is missing' >&2
        exit 2
    fi
fi
# The image contains specialized CUDA binaries for these GPU generations.
cap=$("$smi" --query-gpu=compute_cap --format=csv,noheader | head -n 1)
case "$cap" in
    8.6|8.9) backend=ampere-ada ;;
    12.0) backend=blackwell ;;
    *)
        echo "GPU Compute Capability $cap is not supported by the bundled backends" >&2
        exit 2
        ;;
esac
# Publish only on localhost and mount the persistent model cache. Arguments after
# the image name are forwarded to the container's llama-server entrypoint.
exec podman run \
    -d \
    --name bonsai2-27b \
    "${gpu_args[@]}" \
    -p "127.0.0.1:${BONSAI_PORT:-8080}:8080" \
    -v "$model_dir:/models:rw" \
    -e "BONSAI_CTX_SIZE=$ctx_size" \
    -e "BONSAI_GPU_BACKEND=$backend" \
    -e "BONSAI_REASONING_EFFORT=$reasoning_effort" \
    --security-opt label=disable \
    "$image" \
    "$@"
