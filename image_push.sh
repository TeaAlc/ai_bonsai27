#!/usr/bin/env bash
# Disable shell tracing before handling credentials, even when invoked with -x.
set +x
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/data/logging.sh"
bonsai_init_logging image_push
bonsai_step configuration "Reading options and validating prerequisites."
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

readonly registry_image=ghcr.io/teaalc/ai_bonsai27
username=${BONSAI_GHCR_USER:-TeaAlc}
engine=${BONSAI_PUSH_ENGINE:-auto}
token=''
token_parameter=false

# A token may be supplied explicitly; otherwise prompt for it below.
# Keep tracing disabled so parsing never prints a token into terminal output.
while (( $# > 0 )); do
    case "$1" in
        --token|-t)
            (( $# >= 2 )) || { echo 'Error: --token requires a value.' >&2; exit 2; }
            token=$2
            token_parameter=true
            shift 2
            ;;
        --token=*)
            token=${1#*=}
            token_parameter=true
            shift
            ;;
        --help|-h)
            echo 'Usage: ./image_push.sh [--token TOKEN]'
            echo 'Without --token, the token is requested with hidden input.'
            echo 'BONSAI_GHCR_USER sets the login user (default: TeaAlc).'
            echo 'BONSAI_PUSH_ENGINE selects auto (default), podman, or docker.'
            exit 0
            ;;
        *)
            echo 'Error: unknown option. Use ./image_push.sh --help.' >&2
            exit 2
            ;;
    esac
done

fail() {
    echo "Error: $*" >&2
    exit 2
}

source tools/project.sh
bonsai_step build-selection "Reading the last successful build receipt."
lock_project
readonly receipt_file=results/last-build.json
[[ -r "$receipt_file" ]] || { echo 'Error: missing build receipt; run build.sh.' >&2; exit 2; }
# The last successful build is publishable independently of Git release tags.
# Keep its exact identity even when HEAD or local tags changed after building.
read -r source_id version revision < <(python3 -B - "$receipt_file" <<'PYCODE'
import json, sys
sys.path.insert(0, 'tools')
from registry import validate_receipt
with open(sys.argv[1]) as stream: receipt = json.load(stream)
validate_receipt(receipt)
print(receipt['image_id'], receipt['version'], receipt['revision'])
PYCODE
)
readonly local_image="$source_id"

engine_ready() {
    command -v "$1" >/dev/null 2>&1 && "$1" info >/dev/null 2>&1
}

# Podman and Docker have separate image stores. Prefer a working Podman that
# owns the last build; otherwise use a working Docker daemon.
case "$engine" in
    auto)
        if engine_ready podman && podman image inspect "$local_image" >/dev/null 2>&1; then
            engine=podman
        elif engine_ready docker; then
            engine=docker
        else
            fail 'No usable container engine with a local build. Run ./build.sh first.'
        fi
        ;;
    podman|docker)
        engine_ready "$engine" || fail "The selected $engine engine is unavailable."
        ;;
    *)
        fail 'BONSAI_PUSH_ENGINE must be auto, podman, or docker.'
        ;;
esac

# Credentials and any Podman-to-Docker transfer remain outside the repository.
# Restrict permissions and delete the temporary directory on every exit path.
umask 077
mkdir -p "${TMPDIR:-/tmp/bonsai27}"
work_dir=$(mktemp -d "${TMPDIR:-/tmp/bonsai27}/ghcr-push.XXXXXX")
trap 'rm -rf -- "$work_dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$engine" == docker ]]; then
    mkdir -p "$work_dir/docker"
    engine_command=(docker --config "$work_dir/docker")
    if ! docker image inspect "$source_id" >/dev/null 2>&1; then
        # An explicitly selected Docker can publish a Podman build by importing
        # its docker-archive. No rebuilding or model files are required.
        engine_ready podman || fail 'Docker has no local build and Podman cannot export it.'
        podman image inspect "$local_image" >/dev/null 2>&1 || fail 'No local image. Run ./build.sh first.'
        echo 'Importing the latest Podman build into Docker.'
        podman save --format docker-archive --output "$work_dir/image.tar" "$local_image"
        "${engine_command[@]}" load --input "$work_dir/image.tar"
        rm -- "$work_dir/image.tar"
    fi
else
    engine_command=(podman)
fi

bonsai_step image-verification "Checking exact image identity and source labels."
# Check inspected labels against the build receipt, independent of mutable aliases.
"${engine_command[@]}" image inspect "$source_id" > "$work_dir/image.json"
python3 -B - "$receipt_file" "$work_dir/image.json" <<'PYCODE'
import json, sys
receipt = json.load(open(sys.argv[1]))
image = json.load(open(sys.argv[2]))[0]
labels = image['Config']['Labels']
expected = {'org.opencontainers.image.version': receipt['version'],
            'org.opencontainers.image.revision': receipt['revision'],
            'org.opencontainers.image.source': receipt['source'],
            'io.bonsai.git.dirty': str(receipt['dirty']).lower()}
if 'sha256:' + image['Id'].removeprefix('sha256:') != receipt['image_id'] or any(labels.get(k) != v for k,v in expected.items()):
    raise ValueError('local image does not match the build receipt')
PYCODE

# Prompt when no token parameter was supplied. Registry login receives the
# token through stdin; credentials never enter the repository or permanent
# registry configuration. Temporary authentication is removed on exit.
bonsai_step registry-login "Obtaining temporary registry credentials."
if [[ "$token_parameter" == false ]]; then
    printf 'GHCR token for %s (input hidden): ' "$username" >&2
    if ! IFS= read -r -s token; then
        printf '\n' >&2
        fail 'No token was provided.'
    fi
    printf '\n' >&2
fi
[[ -n "$token" ]] || fail 'The token must not be empty.'

if [[ "$engine" == podman ]]; then
    auth_args=(--authfile "$work_dir/auth.json")
    printf '%s' "$token" | podman login "${auth_args[@]}" \
        ghcr.io --username "$username" --password-stdin
else
    auth_args=()
    printf '%s' "$token" | "${engine_command[@]}" login \
        ghcr.io --username "$username" --password-stdin
fi
# Use a private credential file for registry API checks; never pass its contents
# through command arguments. The EXIT trap removes it and engine credentials.
printf '%s' "$token" | python3 -B -c 'import json,sys; json.dump({"username":sys.argv[2],"token":sys.stdin.read()},open(sys.argv[1],"w"))' "$work_dir/credentials.json" "$username"
unset token
# Every successful build can be published. Version and latest are mutable
# registry aliases, including rebuilds and builds with uncommitted changes.
# Git release tags remain unchanged; they describe commit history for semrel.
bonsai_step version-push "Publishing $registry_image:$version with $engine."
destination="$registry_image:$version"
"${engine_command[@]}" tag "$source_id" "$destination"
echo "Pushing $destination with $engine"
if [[ "$engine" == podman ]]; then
    podman push "${auth_args[@]}" "$source_id" "docker://$destination"
else
    "${engine_command[@]}" push "$destination"
fi
# Promote the exact version manifest via the registry API. This keeps the two
# tags identical for both engines and supports retry after a partial push.
bonsai_step latest-promotion "Verifying the pushed image and updating latest to the same manifest."
digest=$(python3 -B tools/registry.py promote --receipt "$receipt_file" --credentials "$work_dir/credentials.json")
printf 'Published %s:%s and latest; registry digest: %s\n' "$registry_image" "$version" "$digest"
