#!/usr/bin/env bash
set -euo pipefail

# Read container settings. run.sh supplies these values through environment
# variables; defaults also allow the image to be started directly with Podman.
ctx_size=${BONSAI_CTX_SIZE:-16384}
model=${BONSAI_MODEL:-/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf}
vision_projector=${BONSAI_MMPROJ:-/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf}
reasoning_effort=${BONSAI_REASONING_EFFORT:-medium}
source /opt/bonsai/download-models.sh
source /opt/bonsai/detect-gpu.sh

# Detect the visible GPU unless the caller explicitly selected a CUDA bundle.
gpu_backend=$(select_gpu_backend)
echo "Selected GPU backend: $gpu_backend"

fail() {
    echo "Error: $*" >&2
    exit 2
}

# Reject invalid settings before loading model weights or allocating VRAM.
validate_settings() {
    if [[ ! "$ctx_size" =~ ^[0-9]+$ ]]; then
        fail 'BONSAI_CTX_SIZE must be an integer of at least 512'
    fi
    if (( 10#$ctx_size < 512 )); then
        fail 'BONSAI_CTX_SIZE must be at least 512'
    fi

    case "$gpu_backend" in
        blackwell|ampere-ada) ;;
        *) fail "Unknown BONSAI_GPU_BACKEND: $gpu_backend" ;;
    esac

    # Official Bonsai 2 template values: low, medium, xhigh. The model default
    # is xhigh; medium gives shorter reasoning. low may behave like xhigh.
    case "$reasoning_effort" in
        low|medium|xhigh) ;;
        *) fail 'BONSAI_REASONING_EFFORT must be low, medium, or xhigh' ;;
    esac
}

validate_settings

# Use one library search path for preflight and the server. CUDA driver files
# come from the host GPU runtime, never from a stub or bundled host driver.
backend_dir="/opt/bonsai/$gpu_backend"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:$backend_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if ! query_cuda_capability >/dev/null; then
    fail 'CUDA driver/GPU access is unavailable. Docker requires --gpus all and NVIDIA_DRIVER_CAPABILITIES=compute,utility; Podman requires NVIDIA CDI or the WSL /dev/dxg and /usr/lib/wsl mounts. No models were downloaded.'
fi

# Populate the writable model mount before loading the server. Reuse cached
# files; missing files are downloaded from pinned revisions and SHA256-checked.
download_missing_model "$MODEL_REPO/$MODEL_FILE" "$model" "$MODEL_SHA"
download_missing_model "$VISION_REPO/$VISION_FILE" "$vision_projector" "$VISION_SHA"

# Keep the BF16 vision encoder/projector on CPU and in system RAM.
model_args=(
    --model "$model"
    --alias bonsai2-27b
    --mmproj "$vision_projector"
    --no-mmproj-offload
)

# The container listens on port 8080; run.sh publishes it on host localhost.
# One slot gives a single request the configured context window.
server_args=(
    --host 0.0.0.0
    --port 8080
    --ctx-size "$ctx_size"
    --parallel 1
)

# Force every language-model tensor, including embeddings, onto CUDA0.
# Disable automatic memory fitting and CPU prompt caching. Insufficient VRAM
# should fail rather than silently moving language-model weights to the CPU.
gpu_args=(
    --device CUDA0
    --n-gpu-layers all
    --fit off
    --override-tensor '.*=CUDA0'
    --cache-ram 0
    --flash-attn on
    --cache-type-k q8_0
    --cache-type-v q8_0
)

# The GGUF includes an MTP head. Propose at most two tokens per draft, then
# verify them with the main model. Keep the draft and its q8_0 K/V on CUDA0.
mtp_args=(
    --spec-type draft-mtp
    --spec-draft-n-max 2
    --spec-draft-device CUDA0
    --spec-draft-ngl 99
    --spec-draft-type-k q8_0
    --spec-draft-type-v q8_0
)

# Use the model's Jinja chat template and the configured reasoning effort.
generation_args=(
    --jinja
    --reasoning-effort "$reasoning_effort"
    --temp 1.0
    --top-p 0.95
    --top-k 20
)

# Replace the entrypoint process so llama-server receives container stop signals.
# Forward additional arguments last, preserving each argument's quoting.
exec "$backend_dir/bin/llama-server" \
    "${model_args[@]}" \
    "${server_args[@]}" \
    "${gpu_args[@]}" \
    "${mtp_args[@]}" \
    "${generation_args[@]}" \
    "$@"
