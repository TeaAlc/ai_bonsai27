#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/data/logging.sh"
bonsai_init_logging download_models
bonsai_step configuration "Reading options and validating prerequisites."
# Verify/repair applies to the two pinned artifacts, never arbitrary custom GGUFs.
mode=reuse
case "${1:-}" in
    '') ;;
    --verify) mode=verify; shift ;;
    --repair) mode=repair; shift ;;
    --help|-h)
        echo 'Usage: BONSAI_MODEL_DIR=/path/to/models ./download_models.sh [--verify|--repair]'
        echo 'BONSAI_MODEL_VARIANT=ptq1_0 (default) or pq2_0 selects the pinned model.'
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
bonsai_step language-model "Preparing $model_dir/$MODEL_FILE (mode=$mode)."
download_missing_model "$MODEL_REPO/$MODEL_FILE" "$model_dir/$MODEL_FILE" "$MODEL_SHA" "$mode"
bonsai_step vision-model "Preparing $model_dir/$VISION_FILE (mode=$mode)."
download_missing_model "$VISION_REPO/$VISION_FILE" "$model_dir/$VISION_FILE" "$VISION_SHA" "$mode"
echo "Models ready in $model_dir"
