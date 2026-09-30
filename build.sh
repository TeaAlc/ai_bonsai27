#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
source tools/project.sh
source tools/backend-artifacts.sh
lock_project
version=$(./tools/version.sh)
revision=$(git rev-parse HEAD)
dirty=false
[[ -z $(git status --porcelain --untracked-files=normal) ]] || dirty=true
if [[ -n ${BONSAI_RELEASE_REVISION:-} ]]; then
    [[ "$revision" == "$BONSAI_RELEASE_REVISION" && "$version" == "$BONSAI_RELEASE_VERSION" && "$dirty" == false ]] \
        || { echo 'Error: release source/version changed before the build.' >&2; exit 2; }
fi

# Build an immutable snapshot. Clean builds use committed files; development
# builds overlay local files and are recorded as dirty, ineligible for pushing.
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
image="localhost/bonsai2-27b:$version"
echo "Building $image from Git revision $revision (dirty=$dirty)"
podman build --tag "$image" --tag localhost/bonsai2-27b:latest \
    --label "org.opencontainers.image.version=$version" \
    --label "org.opencontainers.image.revision=$revision" \
    --label "io.bonsai.git.dirty=$dirty" \
    --label 'org.opencontainers.image.source=https://github.com/TeaAlc/ai_bonsai27' \
    --file "$staging/Containerfile" "$staging"
podman image inspect "$image" > "$staging/image.json"
image_id=$(python3 -B -c 'import json,sys; print(json.load(open(sys.argv[1]))[0]["Id"])' "$staging/image.json")
podman run --rm --entrypoint dpkg-query "$image_id" -W > "$staging/packages.txt"
mkdir -p results
python3 -B tools/build-receipt.py "$staging" "$version" "$revision" "$dirty" results/last-build.json
printf 'Built %s and latest; receipt: results/last-build.json\n' "$image"
