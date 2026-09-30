#!/usr/bin/env bash
# Disable shell tracing before handling credentials, even when invoked with -x.
set +x
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

readonly local_image=localhost/bonsai2-27b:latest
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
    if ! docker image inspect "$local_image" >/dev/null 2>&1; then
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

# Pin the source image ID, then read the version assigned by semrel at build
# time. Do not calculate a different version from newer, unbuilt Git commits.
source_id=$("${engine_command[@]}" image inspect --format '{{.Id}}' "$local_image")
version=$("${engine_command[@]}" image inspect \
    --format '{{index .Config.Labels "org.opencontainers.image.version"}}' "$source_id")
[[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] \
    || fail 'The local image has no valid semrel version label. Rebuild it with ./build.sh.'

# Prompt when no token parameter was supplied. Registry login receives the
# token through stdin; credentials never enter the repository or permanent
# registry configuration. Temporary authentication is removed on exit.
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
unset token

# Push the version first. Update the remote latest tag only after it succeeds.
# Both destinations refer to the same source image, regardless of local tags.
for tag in "$version" latest; do
    destination="$registry_image:$tag"
    "${engine_command[@]}" tag "$source_id" "$destination"
    echo "Pushing $destination with $engine"
    if [[ "$engine" == podman ]]; then
        podman push "${auth_args[@]}" \
            --digestfile "$work_dir/$tag.digest" \
            "$source_id" "docker://$destination"
    else
        "${engine_command[@]}" push "$destination"
    fi
done
# The Podman path also verifies that both uploaded manifests have the same
# digest. Docker pushes the same image ID under both tags using its own CLI.
if [[ "$engine" == podman ]]; then
    version_digest=$(cat "$work_dir/$version.digest")
    latest_digest=$(cat "$work_dir/latest.digest")
    [[ "$version_digest" == "$latest_digest" ]] || fail 'Uploaded image digests differ.'
    printf 'Registry digest: %s\n' "$version_digest"
fi
printf 'Published %s:%s and %s:latest\n' "$registry_image" "$version" "$registry_image"
