#!/usr/bin/env bash
# Called inside the pinned compiler image by build-blackwell-backend.sh.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends cmake ninja-build g++ git ca-certificates python3
# Check real driver access before compiling. WSL driver paths are injected by
# the host preparation script. Runtime validation must use the real driver.
python3 -B /tools/check-build-cuda.py
cmake -S /work/source -B /work/build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120-real \
    -DGGML_CUDA_FA=ON -DGGML_CUDA_FA_ALL_QUANTS=OFF -DGGML_CUDA_GRAPHS=ON \
    -DLLAMA_CURL=OFF -DLLAMA_BUILD_UI=OFF -DGGML_NATIVE=OFF \
    -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON
cmake --build /work/build --target llama-server test-backend-ops -j "$BONSAI_BUILD_JOBS"
python3 -B /tools/package-blackwell-backend.py /work
