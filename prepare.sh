#!/usr/bin/env bash
set -euo pipefail
# Preserve the caller's model directory while keeping backend paths in the repo.
export BONSAI_MODEL_DIR=${BONSAI_MODEL_DIR:-"$PWD"}
mkdir -p -- "$BONSAI_MODEL_DIR"
BONSAI_MODEL_DIR=$(cd -- "$BONSAI_MODEL_DIR" && pwd)
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Keep temporary files for Podman and helper tools outside the project.
export TMPDIR="${TMPDIR:-/tmp/bonsai27}"
mkdir -p "$TMPDIR"

# Share pinned model metadata with the container download helper.
source data/models/download.sh

# -C - resumes interrupted downloads; SHA256 catches stale or corrupt files.
download_checked() {
    local url=$1 destination=$2 expected_sha=$3
    echo "Downloading/checking $destination"
    curl -fL --retry 4 -C - "$url" -o "$destination"
    printf '%s  %s\n' "$expected_sha" "$destination" | sha256sum -c -
}

# Each CUDA bundle contains its own checksums for extracted files.
extract_backend() {
    local archive=$1 destination=$2
    mkdir -p "$destination"
    tar -xzf "$archive" --strip-components=1 -C "$destination"
    (cd "$destination" && sha256sum -c SHA256SUMS)
}

mkdir -p data/backends/blackwell data/backends/ampere-ada results
./download_models.sh

# sm120: Blackwell/RTX 50. sm86/sm89: supported Ampere/Ada GPUs.
download_checked "$MODEL_REPO/bonsai2-small-gpu-linux-x64-cuda12.8-sm120-ff41412.tar.gz" \
    data/backends/blackwell/archive.tar.gz \
    74e1cf451d41e1435d15ef93e76007219cdf28fd1eb59bf335d1f3d31bfbc4da
extract_backend data/backends/blackwell/archive.tar.gz data/backends/blackwell/runtime

download_checked "$MODEL_REPO/bonsai2-small-gpu-linux-x64-cuda12.4-sm86-sm89-285542d.tar.gz" \
    data/backends/ampere-ada/archive.tar.gz \
    46b0bc960f00352267ed34246b7cb5010fa64618077158647e5d2bbcf0fb60fe
extract_backend data/backends/ampere-ada/archive.tar.gz data/backends/ampere-ada/runtime

echo 'Preparation complete. Build the image with ./build.sh.'
