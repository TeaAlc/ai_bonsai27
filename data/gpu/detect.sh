#!/usr/bin/env bash
# Choose the bundle for the first GPU visible inside the container. An explicit
# setting must match the detected compute capability. The CUDA driver probe works without nvidia-smi.
query_cuda_capability() {
    LD_LIBRARY_PATH="/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        /opt/bonsai/cuda-compute-capability
}

select_gpu_backend() {
    local requested=${BONSAI_GPU_BACKEND:-} smi capability
    # Prefer the driver query: it uses CUDA device ordering, honors visibility,
    # and needs only the driver libraries already required by llama-server.
    if capability=$(query_cuda_capability); then
        :
    elif smi=$(command -v nvidia-smi); then
        if ! capability=$("$smi" --id=0 --query-gpu=compute_cap --format=csv,noheader); then
            echo 'Error: cannot query the GPU. Check container GPU access.' >&2
            return 2
        fi
    elif [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
        if ! capability=$(LD_LIBRARY_PATH="/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
            /usr/lib/wsl/lib/nvidia-smi --id=0 --query-gpu=compute_cap --format=csv,noheader); then
            echo 'Error: cannot query the GPU. Check container GPU access.' >&2
            return 2
        fi
    else
        echo 'Error: CUDA driver/GPU access is unavailable; detection failed through CUDA and nvidia-smi. Check GPU passthrough and driver libraries, or set BONSAI_GPU_BACKEND explicitly.' >&2
        return 2
    fi
    capability=${capability//[[:space:]]/}
    local detected
    case "$capability" in
        8.6|8.9) detected=ampere-ada ;;
        12.0) detected=blackwell ;;
        *) echo "Error: unsupported GPU compute capability: $capability" >&2; return 2 ;;
    esac
    if [[ -n "$requested" && "$requested" != "$detected" ]]; then
        echo "Error: BONSAI_GPU_BACKEND=$requested does not match CUDA device 0 ($capability; expected $detected)." >&2
        return 2
    fi
    printf '%s\n' "$detected"
}
