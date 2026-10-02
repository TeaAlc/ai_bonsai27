#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/data/logging.sh"
bonsai_init_logging build
bonsai_step configuration "Reading options and validating prerequisites."
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
source tools/project.sh
source tools/backend-artifacts.sh
# Keep the published bundles as the default; opt in to the researched SM89 build.
ada_source=false
case "${1:-}" in
    '') (( $# == 0 )) || exit 2 ;;
    --ada-source) (( $# == 1 )) || exit 2; ada_source=true ;;
    *) echo 'Usage: image_build.sh [--ada-source]' >&2; exit 2 ;;
esac
bonsai_step project-lock "Waiting for the checkout lock."
lock_project
bonsai_step version "Calculating the image version with semrel."
version=$(./tools/version.sh)
revision=$(git rev-parse HEAD)
dirty=false
[[ -z $(git status --porcelain --untracked-files=normal) ]] || dirty=true
if [[ -n ${BONSAI_RELEASE_REVISION:-} ]]; then
    [[ "$revision" == "$BONSAI_RELEASE_REVISION" && "$version" == "$BONSAI_RELEASE_VERSION" && "$dirty" == false ]] \
        || { echo 'Error: release source/version changed before the build.' >&2; exit 2; }
fi

# Build an immutable snapshot. Clean builds use committed files; development
# builds overlay local files and are recorded as dirty, publishable with their dirty label.
bonsai_step source-snapshot "Snapshotting project sources."
staging=$(mktemp -d "$TMPDIR/build.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT
git archive "$revision" | tar -x -C "$staging"
if [[ "$dirty" == true ]]; then
    python3 -B - "$staging" <<'PY'
import pathlib, shutil, subprocess, sys
root = pathlib.Path(sys.argv[1])
files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).split(b'\0')
for name in files:
    if not name: continue
    path = pathlib.Path(name.decode())
    target = root / path
    if path.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    elif target.exists(): target.unlink()
PY
fi

# Snapshot and verify all backend files against the pinned manifest identity.
bonsai_step backend-verification "Snapshotting and verifying both pinned backends."
for backend in blackwell ampere-ada; do
    source_dir="data/backends/$backend/runtime"
    if [[ ! -d "$source_dir" && -d "data/backends/$backend/runtime.previous" ]]; then
        mv -- "data/backends/$backend/runtime.previous" "$source_dir"
    fi
    [[ -d "$source_dir" ]] || { echo "Error: missing $backend; run prepare.sh." >&2; exit 2; }
    mkdir -p "$staging/data/backends/$backend"
    cp -a --reflink=auto "$source_dir" "$staging/data/backends/$backend/runtime"
    actual=$(python3 -B tools/verify-backend.py "$staging/data/backends/$backend/runtime")
    expected=$BLACKWELL_MANIFEST_SHA
    [[ "$backend" != ampere-ada ]] || expected=$AMPERE_ADA_MANIFEST_SHA
    [[ "$actual" == "$expected" ]] || { echo "Error: unpinned $backend manifest." >&2; exit 2; }
done
# Include the optional source backend without changing either upstream bundle.
mkdir -p "$staging/data/backends/ada-source/runtime"
if [[ "$ada_source" == true ]]; then
    source_dir=data/backends/ada-source/runtime
    [[ -f "$source_dir/SHA256SUMS" ]] \
        || { echo 'Error: missing Ada source backend; run tools/build-ada-backend.sh.' >&2; exit 2; }
    python3 -B tools/verify-ada-source.py "$source_dir"
    cp -a --reflink=auto "$source_dir/." "$staging/data/backends/ada-source/runtime/"
    python3 -B tools/verify-ada-source.py "$staging/data/backends/ada-source/runtime"
fi
image="localhost/bonsai2-27b:$version"
echo "Building $image from Git revision $revision (dirty=$dirty)"
bonsai_step image-build "Building $image and latest (revision=$revision; dirty=$dirty)."
podman build --tag "$image" --tag localhost/bonsai2-27b:latest \
    --label "org.opencontainers.image.version=$version" \
    --label "org.opencontainers.image.revision=$revision" \
    --label "io.bonsai.git.dirty=$dirty" \
    --label 'org.opencontainers.image.source=https://github.com/TeaAlc/ai_bonsai27' \
    --file "$staging/Containerfile" "$staging"
bonsai_step build-receipt "Inspecting the built image and recording package inventory."
podman image inspect "$image" > "$staging/image.json"
image_id=$(python3 -B -c 'import json,sys; print(json.load(open(sys.argv[1]))[0]["Id"])' "$staging/image.json")
podman run --rm --entrypoint dpkg-query "$image_id" -W > "$staging/packages.txt"
mkdir -p results
python3 -B tools/build-receipt.py "$staging" "$version" "$revision" "$dirty" results/last-build.json
printf 'Built %s and latest; receipt: results/last-build.json\n' "$image"
