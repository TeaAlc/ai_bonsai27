#!/usr/bin/env bash
# Shared, pinned model artifacts for host preparation and container startup.
readonly MODEL_REVISION=f04a3bd22b7b482675663e99efaba6719347b419
readonly VISION_REVISION=b072e1d3b35a0a630cece372c2127528e0994386
readonly MODEL_REPO=https://huggingface.co/sudoingx/Ternary-Bonsai-2-27B-PTQ1_0-MTP-GGUF/resolve/$MODEL_REVISION
readonly VISION_REPO=https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/$VISION_REVISION
readonly MODEL_FILE=Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf
readonly VISION_FILE=Ternary-Bonsai-2-27B-mmproj-BF16.gguf
readonly MODEL_SHA=1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685
readonly VISION_SHA=e287342d92332fa3577ed1d42e921dac9370c08da58ba9337fa450f6cc76cfd7

# Existing nonempty files are reused without network access. A per-file lock
# prevents competing containers from downloading into the same cache at once.
# Keep interrupted downloads beside the destination so curl can resume them;
# publish a file atomically only after its checksum has passed.
download_missing_model() (
    set -euo pipefail
    local url=$1 destination=$2 expected_sha=$3
    [[ -s "$destination" && -r "$destination" ]] && exit 0
    mkdir -p -- "$(dirname -- "$destination")"
    exec 9>"$destination.lock"
    flock 9
    [[ -s "$destination" && -r "$destination" ]] && exit 0
    echo "Downloading missing model: $destination"
    curl --fail --location --retry 4 --continue-at - \
        --output "$destination.part" "$url"
    if ! printf '%s  %s\n' "$expected_sha" "$destination.part" | sha256sum -c -; then
        rm -f -- "$destination.part"
        echo "Error: model checksum failed: $destination" >&2
        exit 2
    fi
    mv -- "$destination.part" "$destination"
)
