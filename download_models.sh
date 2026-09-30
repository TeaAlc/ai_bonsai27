#!/usr/bin/env bash
set -euo pipefail

# Use the caller's current directory unless a persistent cache is specified.
if (( $# > 0 )); then
    if [[ $# == 1 && "$1" == --help ]]; then
        echo 'Usage: BONSAI_MODEL_DIR=/path/to/models ./download_models.sh'
        echo 'Without BONSAI_MODEL_DIR, models are saved in the current directory.'
        exit 0
    fi
    echo 'Error: use BONSAI_MODEL_DIR to select the download directory.' >&2
    exit 2
fi
model_dir=${BONSAI_MODEL_DIR:-"$PWD"}
mkdir -p -- "$model_dir"
model_dir=$(cd -- "$model_dir" && pwd)
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/data/models/download.sh"

# Download only missing files using the same pins and verification as startup.
download_missing_model "$MODEL_REPO/$MODEL_FILE" "$model_dir/$MODEL_FILE" "$MODEL_SHA"
download_missing_model "$VISION_REPO/$VISION_FILE" "$model_dir/$VISION_FILE" "$VISION_SHA"
echo "Models ready in $model_dir"
