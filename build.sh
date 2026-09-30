#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Keep Podman temporary build files outside the project.
export TMPDIR="${TMPDIR:-/tmp/bonsai27}"
mkdir -p "$TMPDIR"

# semrel calculates the project version from committed history and release tags.
# This is independent of the pinned llama-server backend commit.
version=$(./tools/version.sh)
revision=$(git rev-parse HEAD)
# Local edits are built too, but semrel only analyzes committed changes.
dirty=false
if [[ -n $(git status --porcelain --untracked-files=normal) ]]; then
    dirty=true
fi
image="localhost/bonsai2-27b:$version"
echo "Building $image from Git revision $revision"

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

# Build one image with both the semrel version and latest tags. Podman applies
# both tags to the successful result; OCI labels keep the version inspectable.
podman build \
    --tag "$image" \
    --tag localhost/bonsai2-27b:latest \
    --label "org.opencontainers.image.version=$version" \
    --label "org.opencontainers.image.revision=$revision" \
    --label "io.bonsai.git.dirty=$dirty" \
    --label 'org.opencontainers.image.source=https://github.com/TeaAlc/ai_bonsai27' \
    --file Containerfile \
    .
printf 'Built %s (also available as localhost/bonsai2-27b:latest)\n' "$image"
