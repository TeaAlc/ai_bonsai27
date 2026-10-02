#!/usr/bin/env bash
# Compile an allowlisted native backend inside the pinned compiler image.
set -euo pipefail
profile=${1:?Expected ada or blackwell}
case "$profile" in ada|blackwell) ;; *) echo 'Error: unknown backend profile.' >&2; exit 2 ;; esac
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends cmake ninja-build g++ git ca-certificates python3
# Check real driver access before compiling. WSL driver paths are injected by
# the host preparation script. Runtime validation must use the real driver.
architecture=$(python3 -B /tools/backend_profile.py "$profile" architecture)
python3 -B /tools/check-build-cuda.py
cmake -S /work/source -B /work/build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="$architecture" \
    -DGGML_CUDA_FA=ON -DGGML_CUDA_FA_ALL_QUANTS=OFF -DGGML_CUDA_GRAPHS=ON \
    -DLLAMA_CURL=OFF -DLLAMA_BUILD_UI=OFF -DGGML_NATIVE=OFF \
    -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON
cmake --build /work/build --target llama-server test-backend-ops -j "$BONSAI_BUILD_JOBS"
python3 -B /tools/package-backend.py /work "$profile"
