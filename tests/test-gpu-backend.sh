#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/data/gpu/detect.sh"

# Mock the GPU query, while exercising the production selection logic.
nvidia-smi() {
    [[ "$*" == '--id=0 --query-gpu=compute_cap --format=csv,noheader' ]] || return 1
    [[ ${query_failure:-false} == false ]] || return 1
    printf ' %s\n' "$fixture_capability"
}
unset BONSAI_GPU_BACKEND
for fixture_capability in 8.6 8.9 12.0; do
    expected=ampere-ada
    [[ "$fixture_capability" == 12.0 ]] && expected=blackwell
    [[ $(select_gpu_backend) == "$expected" ]]
done
fixture_capability=7.5
if select_gpu_backend; then exit 1; fi
query_failure=true
if select_gpu_backend; then exit 1; fi
for override in blackwell ampere-ada; do
    [[ $(BONSAI_GPU_BACKEND=$override select_gpu_backend) == "$override" ]]
done
if BONSAI_GPU_BACKEND=invalid select_gpu_backend; then exit 1; fi
echo 'Passed GPU detection, unsupported GPU, query failure, and override checks.'
