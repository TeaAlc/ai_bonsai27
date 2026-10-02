#!/usr/bin/env bash
set -euo pipefail
source /opt/bonsai/logging.sh
bonsai_init_logging startup
bonsai_step configuration "Validating container settings."

# Read container settings. run.sh supplies these values through environment
# variables; defaults also allow the image to be started directly with Podman.
ctx_size=${BONSAI_CTX_SIZE:-16384}
model=${BONSAI_MODEL:-/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf}
vision_projector=${BONSAI_MMPROJ:-/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf}
reasoning_effort=${BONSAI_REASONING_EFFORT:-medium}
source /opt/bonsai/download-models.sh
source /opt/bonsai/detect-gpu.sh

# Validate input before driver initialization or downloading large artifacts.
source /opt/bonsai/settings.sh
validate_bonsai_settings
ctx_size=$((10#$ctx_size))
fail() { bonsai_log ERROR "$*"; exit 2; }
bonsai_log INFO "Context=$ctx_size; reasoning=$reasoning_effort; requested backend=${BONSAI_GPU_BACKEND:-auto}."

# Check cache paths before GPU initialization, without starting any transfer.
bonsai_step model-cache "Checking model paths and write access for missing files."
for artifact_path in "$model" "$vision_projector"; do
    if [[ -s "$artifact_path" && -r "$artifact_path" ]]; then
        bonsai_log INFO "Reusable cache file: $artifact_path"
        continue
    fi
    cache_parent=$(dirname -- "$artifact_path")
    mkdir -p -- "$cache_parent" || fail "Cannot create model directory: $cache_parent"
    cache_probe=$(mktemp "$cache_parent/.bonsai-write-check.XXXXXX") \
        || fail "Model cache is not writable: $cache_parent. Check write access."
    rm -- "$cache_probe"
done

bonsai_step gpu-access "Checking CUDA device 0; a backend override does not supply driver libraries or GPU devices."
bonsai_log INFO "Driver library search: /usr/lib/wsl/lib, /usr/local/nvidia/lib, /usr/local/nvidia/lib64, system loader paths."
for gpu_path in /dev/dxg /dev/nvidia0 /usr/lib/wsl/lib/libcuda.so.1; do
    if [[ -e "$gpu_path" ]]; then
        bonsai_log INFO "GPU runtime path present: $gpu_path"
    else
        bonsai_log INFO "GPU runtime path absent: $gpu_path"
    fi
done
# Capture diagnostics separately from the backend name written to stdout.
if gpu_backend=$(select_gpu_backend); then
    :
else
    fail 'CUDA driver/GPU access is unavailable. Podman Desktop needs NVIDIA Toolkit/CDI in its machine, or the WSL device and driver mount. Docker needs GPU runtime injection. BONSAI_GPU_BACKEND cannot provide GPU access. No models were downloaded.'
fi
bonsai_log INFO "Selected GPU backend: $gpu_backend"

# Use one library search path for preflight and the server. CUDA driver files
# come from the host GPU runtime, never from a stub or bundled host driver.
backend_dir="/opt/bonsai/$gpu_backend"
# The optional native SM89 build is selected only for an Ada device. Ampere
# and Blackwell retain their pinned published bundles and CUDA architectures.
if [[ "$gpu_backend" == ampere-ada && -x /opt/bonsai/ada-source/bin/llama-server ]]; then
    if [[ $(query_cuda_capability) == 8.9 ]]; then
        backend_dir=/opt/bonsai/ada-source
        bonsai_log INFO 'Using the optional pinned Prism source backend for SM89.'
    fi
fi
# Native SM120 code and the newer Prism kernels are used only on Blackwell.
if [[ "$gpu_backend" == blackwell && -x /opt/bonsai/blackwell-source/bin/llama-server ]]; then
    backend_dir=/opt/bonsai/blackwell-source
    bonsai_log INFO 'Using the pinned Prism source backend for SM120.'
fi
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:$backend_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if ! query_cuda_capability >/dev/null; then
    fail 'CUDA driver/GPU access is unavailable. Docker requires --gpus all and NVIDIA_DRIVER_CAPABILITIES=compute,utility; Podman requires NVIDIA CDI or the WSL /dev/dxg and /usr/lib/wsl mounts. No models were downloaded.'
fi

bonsai_step runtime-dependencies "Checking the selected $gpu_backend server and shared libraries."
[[ -x "$backend_dir/bin/llama-server" ]] || fail "Missing executable: $backend_dir/bin/llama-server"
runtime_dependencies=$(ldd "$backend_dir/bin/llama-server")
if [[ "$runtime_dependencies" == *'not found'* ]]; then
    printf '%s\n' "$runtime_dependencies" >&2
    fail 'Selected backend has unresolved shared libraries.'
fi

# Populate the writable model mount before loading the server. Reuse cached
# files; missing files are downloaded from pinned revisions and SHA256-checked.
# While downloading, PID 1 forwards stop signals and waits for child cleanup.
download_pid=''
stop_download() {
    local status=$1
    bonsai_log WARN "Stop requested during model preparation; cancelling the downloader (exit=$status)."
    if [[ -n "$download_pid" ]]; then
        kill -TERM "$download_pid" 2>/dev/null || true
        wait "$download_pid" 2>/dev/null || true
    fi
    exit "$status"
}
trap 'stop_download 143' TERM
trap 'stop_download 130' INT
bonsai_step models "Preparing pinned language and BF16 vision models; existing readable files are reused."
for artifact in model vision; do
    if [[ "$artifact" == model ]]; then
        download_missing_model "$MODEL_REPO/$MODEL_FILE" "$model" "$MODEL_SHA" &
    else
        download_missing_model "$VISION_REPO/$VISION_FILE" "$vision_projector" "$VISION_SHA" &
    fi
    download_pid=$!
    if wait "$download_pid"; then
        bonsai_log INFO "$artifact model ready."
    else
        download_status=$?
        fail "$artifact model preparation failed (exit=$download_status). Partial files remain resumable."
    fi
    download_pid=''
done
trap - TERM INT

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
    # A fixed single-device split avoids free-memory normalization (0/0)
    # when the WSL driver reports no remaining space during draft loading.
    --split-mode none
    --tensor-split 1
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
bonsai_step server "Starting llama-server: backend=${backend_dir##*/}; context=$ctx_size; reasoning=$reasoning_effort; GPU-only LLM; CPU vision; MTP=2; Flash Attention=on; KV=q8_0."
bonsai_log INFO 'Loading the model may take time. The API is ready only when /health returns HTTP 200.'
exec "$backend_dir/bin/llama-server" \
    "${model_args[@]}" \
    "${server_args[@]}" \
    "${gpu_args[@]}" \
    "${mtp_args[@]}" \
    "${generation_args[@]}" \
    "$@"
