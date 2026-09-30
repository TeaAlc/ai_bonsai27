#!/usr/bin/env bash
set -euo pipefail
# Verify/repair applies to the two pinned artifacts, never arbitrary custom GGUFs.
mode=reuse
case "${1:-}" in
    '') ;;
    --verify) mode=verify; shift ;;
    --repair) mode=repair; shift ;;
    --help|-h)
        echo 'Usage: BONSAI_MODEL_DIR=/path/to/models ./download_models.sh [--verify|--repair]'
        echo 'Default: reuse readable nonempty files; --verify hashes without downloading.'
        echo '--repair replaces damaged pinned files only after a verified download.'
        exit 0 ;;
    *) echo 'Error: unknown option. Use --help.' >&2; exit 2 ;;
esac
(( $# == 0 )) || { echo 'Error: unexpected arguments.' >&2; exit 2; }
model_dir=${BONSAI_MODEL_DIR:-"$PWD"}
mkdir -p -- "$model_dir"
model_dir=$(cd -- "$model_dir" && pwd)
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/data/models/download.sh"
download_missing_model "$MODEL_REPO/$MODEL_FILE" "$model_dir/$MODEL_FILE" "$MODEL_SHA" "$mode"
download_missing_model "$VISION_REPO/$VISION_FILE" "$model_dir/$VISION_FILE" "$VISION_SHA" "$mode"
echo "Models ready in $model_dir"
