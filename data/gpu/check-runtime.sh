#!/usr/bin/env bash
set -euo pipefail

# Build-time checks may omit only the host-provided CUDA driver. With GPU
# passthrough, run without arguments to check the complete dependency closure.
allow_missing_driver=false
if [[ $# == 1 && "$1" == --allow-missing-driver ]]; then
    allow_missing_driver=true
elif (( $# != 0 )); then
    echo 'Usage: check-runtime.sh [--allow-missing-driver]' >&2
    exit 2
fi

for tool in bash curl sha256sum flock ldd; do
    command -v "$tool" >/dev/null || { echo "Error: missing runtime tool: $tool" >&2; exit 2; }
done
[[ -s /etc/ssl/certs/ca-certificates.crt ]] \
    || { echo 'Error: HTTPS CA certificates are missing.' >&2; exit 2; }

initial_library_path=${LD_LIBRARY_PATH:-}
backends=(blackwell ampere-ada)
[[ ! -x /opt/bonsai/ada-source/bin/llama-server ]] || backends+=(ada-source)
for backend in "${backends[@]}"; do
    export LD_LIBRARY_PATH="/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/opt/bonsai/$backend/lib${initial_library_path:+:$initial_library_path}"
    for binary in "/opt/bonsai/$backend/bin/llama-server" /opt/bonsai/"$backend"/lib/*.so*; do
        # Ignore no dependencies other than the explicitly allowed host driver.
        missing=$(ldd "$binary" | awk -v allow="$allow_missing_driver" \
            '/=> not found/ { if (!(allow == "true" && $1 == "libcuda.so.1")) print }')
        if [[ -n "$missing" ]]; then
            printf 'Error: missing dependencies for %s:\n%s\n' "$binary" "$missing" >&2
            exit 2
        fi
    done
    echo "Runtime dependencies verified: $backend"
done
