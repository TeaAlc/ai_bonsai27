#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Keep temporary files for Podman and helper tools outside the project.
export TMPDIR="${TMPDIR:-/tmp/bonsai27}"
mkdir -p "$TMPDIR"

# Pin artifact revisions for reproducible downloads.
readonly MODEL_REVISION=f04a3bd22b7b482675663e99efaba6719347b419
readonly VISION_REVISION=b072e1d3b35a0a630cece372c2127528e0994386
readonly MODEL_REPO=https://huggingface.co/sudoingx/Ternary-Bonsai-2-27B-PTQ1_0-MTP-GGUF/resolve/$MODEL_REVISION
readonly VISION_REPO=https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/$VISION_REVISION
readonly MODEL_FILE=Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf
readonly VISION_FILE=Ternary-Bonsai-2-27B-mmproj-BF16.gguf

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

mkdir -p models data/backends/blackwell data/backends/ampere-ada results

download_checked "$MODEL_REPO/$MODEL_FILE" "models/$MODEL_FILE" \
    1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685
download_checked "$VISION_REPO/$VISION_FILE" "models/$VISION_FILE" \
    e287342d92332fa3577ed1d42e921dac9370c08da58ba9337fa450f6cc76cfd7

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
