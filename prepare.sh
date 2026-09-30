#!/usr/bin/env bash
set -euo pipefail
# Resolve the model cache before switching to project-relative backend paths.
export BONSAI_MODEL_DIR=${BONSAI_MODEL_DIR:-"$PWD"}
mkdir -p -- "$BONSAI_MODEL_DIR"
BONSAI_MODEL_DIR=$(cd -- "$BONSAI_MODEL_DIR" && pwd)
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
source tools/project.sh
source tools/backend-artifacts.sh
source data/models/download.sh
lock_project
./download_models.sh

# Download/verify with the same resumable, locked helper as the model cache.
# Extract into a fresh directory; the project lock protects builds and prepares.
prepare_backend() {
    local backend=$1 archive_name=$2 expected_sha=$3 directory staging backup
    directory="data/backends/$backend"
    mkdir -p "$directory"
    backup="$directory/runtime.previous"
    if [[ ! -d "$directory/runtime" && -d "$backup" ]]; then mv -- "$backup" "$directory/runtime"; fi
    download_missing_model "$MODEL_REPO/$archive_name" "$directory/archive.tar.gz" "$expected_sha" repair
    staging=$(mktemp -d "$TMPDIR/backend-$backend.XXXXXX")
    backup="$directory/runtime.previous"
    if ! tar -xzf "$directory/archive.tar.gz" --strip-components=1 -C "$staging" \
        || ! python3 -B tools/verify-backend.py "$staging"; then
        rm -rf -- "$staging"
        return 2
    fi
    # Recovery from an interrupted replacement preserves the last verified tree.
    if [[ ! -d "$directory/runtime" && -d "$backup" ]]; then mv -- "$backup" "$directory/runtime"; fi
    rm -rf -- "$backup"
    if [[ -d "$directory/runtime" ]]; then mv -- "$directory/runtime" "$backup"; fi
    if ! mv -- "$staging" "$directory/runtime"; then
        [[ ! -d "$backup" ]] || mv -- "$backup" "$directory/runtime"
        rm -rf -- "$staging"
        return 2
    fi
    rm -rf -- "$backup"
}
prepare_backend blackwell "$BLACKWELL_ARCHIVE" "$BLACKWELL_SHA"
prepare_backend ampere-ada "$AMPERE_ADA_ARCHIVE" "$AMPERE_ADA_SHA"
echo 'Preparation complete. Build the image with ./build.sh.'
