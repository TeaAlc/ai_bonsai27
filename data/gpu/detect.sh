#!/usr/bin/env bash
# Choose the bundle for the first GPU visible inside the container. An explicit
# setting bypasses detection, allowing hosts with no nvidia-smi to select it.
select_gpu_backend() {
    local requested=${BONSAI_GPU_BACKEND:-} smi capability
    if [[ -n "$requested" ]]; then
        case "$requested" in
            blackwell|ampere-ada) printf '%s\n' "$requested"; return 0 ;;
            *) echo "Error: unknown BONSAI_GPU_BACKEND: $requested" >&2; return 2 ;;
        esac
    fi

    if smi=$(command -v nvidia-smi); then
        :
    elif [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
        smi=/usr/lib/wsl/lib/nvidia-smi
    else
        echo 'Error: GPU detection needs nvidia-smi. Check GPU access or set BONSAI_GPU_BACKEND explicitly.' >&2
        return 2
    fi

    # WSL's tool also needs the mounted driver libraries before backend selection.
    if ! capability=$(LD_LIBRARY_PATH="/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        "$smi" --id=0 --query-gpu=compute_cap --format=csv,noheader); then
        echo 'Error: cannot query the GPU. Check container GPU access.' >&2
        return 2
    fi
    capability=${capability//[[:space:]]/}
    case "$capability" in
        8.6|8.9) echo ampere-ada ;;
        12.0) echo blackwell ;;
        *) echo "Error: unsupported GPU compute capability: $capability" >&2; return 2 ;;
    esac
}
