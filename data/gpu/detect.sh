#!/usr/bin/env bash
# Choose the bundle for the first GPU visible inside the container. An explicit
# setting bypasses detection. The CUDA driver probe works without nvidia-smi.
query_cuda_capability() {
    LD_LIBRARY_PATH="/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        /opt/bonsai/cuda-compute-capability
}

select_gpu_backend() {
    local requested=${BONSAI_GPU_BACKEND:-} smi capability
    if [[ -n "$requested" ]]; then
        case "$requested" in
            blackwell|ampere-ada) printf '%s\n' "$requested"; return 0 ;;
            *) echo "Error: unknown BONSAI_GPU_BACKEND: $requested" >&2; return 2 ;;
        esac
    fi

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
        echo 'Error: GPU detection failed through CUDA and nvidia-smi. Check GPU passthrough and driver libraries, or set BONSAI_GPU_BACKEND explicitly.' >&2
        return 2
    fi
    capability=${capability//[[:space:]]/}
    case "$capability" in
        8.6|8.9) echo ampere-ada ;;
        12.0) echo blackwell ;;
        *) echo "Error: unsupported GPU compute capability: $capability" >&2; return 2 ;;
    esac
}
