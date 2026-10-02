#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/data/logging.sh"
bonsai_init_logging build
bonsai_step configuration "Reading options and validating prerequisites."
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export TMPDIR=${TMPDIR:-/tmp/bonsai27}
source tools/project.sh
source tools/backend-artifacts.sh
# Preserve prepared source runtimes by default. Explicit flags require them;
# --published-only intentionally builds only the two original bundles.
ada_source=auto
blackwell_source=auto
for option in "$@"; do
    case "$option" in
        --ada-source) ada_source=true ;;
        --blackwell-source) blackwell_source=true ;;
        --published-only) ada_source=false; blackwell_source=false ;;
        *) echo 'Usage: image_build.sh [--ada-source] [--blackwell-source] [--published-only]' >&2; exit 2 ;;
    esac
done
bonsai_step project-lock "Waiting for the checkout lock."
lock_project
# Resolve automatic inclusion only after preparation/build operations finish.
# Recover a complete previous tree when an interrupted replacement left none.
for backend in ada blackwell; do
    source_dir="data/backends/$backend-source/runtime"
    if [[ ! -d "$source_dir" && -d "$source_dir.previous" ]]; then
        mv -- "$source_dir.previous" "$source_dir"
    fi
done
if [[ "$ada_source" == auto ]]; then
    ada_source=false
    [[ ! -d data/backends/ada-source/runtime ]] || ada_source=true
fi
if [[ "$blackwell_source" == auto ]]; then
    blackwell_source=false
    [[ ! -d data/backends/blackwell-source/runtime ]] || blackwell_source=true
fi
bonsai_step version "Calculating the image version with semrel."
version=$(./tools/version.sh)
revision=$(git rev-parse HEAD)
dirty=false
[[ -z $(git status --porcelain --untracked-files=normal) ]] || dirty=true
if [[ -n ${BONSAI_RELEASE_REVISION:-} ]]; then
    [[ "$revision" == "$BONSAI_RELEASE_REVISION" && "$version" == "$BONSAI_RELEASE_VERSION" && "$dirty" == false ]] \
        || { echo 'Error: release source/version changed before the build.' >&2; exit 2; }
fi

# The snapshot and one image-layer spool must fit together in TMPDIR. This
# matters on WSL hosts where /tmp is a small RAM filesystem.
bonsai_step temporary-space "Checking space for backend snapshots and image-layer temporary files."
python3 -B - "$TMPDIR" "$ada_source" "$blackwell_source" <<'PYSPACE'
import sys
from pathlib import Path
import shutil

names = ['blackwell', 'ampere-ada']
if sys.argv[2] == 'true':
    names.append('ada-source')
if sys.argv[3] == 'true':
    names.append('blackwell-source')
sizes = []
for name in names:
    runtime = Path('data/backends') / name / 'runtime'
    sizes.append(sum(path.stat().st_size for path in runtime.rglob('*') if path.is_file()))
required = sum(sizes) + max(sizes, default=0) + 256 * 1024 * 1024
available = shutil.disk_usage(sys.argv[1]).free
if available < required:
    raise SystemExit(f'Error: TMPDIR requires approximately {required / 2**30:.2f} GiB free; only {available / 2**30:.2f} GiB available. Remove unused temporary build files or set TMPDIR to a larger filesystem.')
print(f'Temporary space: {available / 2**30:.2f} GiB free; approximately {required / 2**30:.2f} GiB required.', file=sys.stderr)
PYSPACE

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
# Verify each architecture-specific runtime without modifying published bundles.
for backend in ada blackwell; do
    destination="$staging/data/backends/$backend-source/runtime"
    mkdir -p "$destination"
    enabled=$ada_source
    [[ "$backend" != blackwell ]] || enabled=$blackwell_source
    if [[ "$enabled" == true ]]; then
        source_dir="data/backends/$backend-source/runtime"
        [[ -f "$source_dir/SHA256SUMS" ]] \
            || { echo "Error: missing $backend source backend; run tools/build-$backend-backend.sh." >&2; exit 2; }
        bonsai_log INFO "Including the specialized $backend runtime."
        python3 -B "tools/verify-$backend-source.py" "$source_dir"
        cp -a --reflink=auto "$source_dir/." "$destination/"
        python3 -B "tools/verify-$backend-source.py" "$destination"
    fi
done
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
