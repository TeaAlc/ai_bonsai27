#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Keep Podman temporary build files outside the project.
export TMPDIR="${TMPDIR:-/tmp/bonsai27}"
mkdir -p "$TMPDIR"

readonly IMAGE=localhost/bonsai2-27b:ff41412

# The Containerfile copies only extracted backends. Catch missing or corrupt
# files before building the image.
for backend in blackwell ampere-ada; do
    runtime="data/backends/$backend/runtime"
    if [[ ! -f "$runtime/SHA256SUMS" ]]; then
        echo "Backend $backend is missing. Run ./prepare.sh first." >&2
        exit 2
    fi
    (cd "$runtime" && sha256sum -c SHA256SUMS)
done

podman build -t "$IMAGE" -f Containerfile .
