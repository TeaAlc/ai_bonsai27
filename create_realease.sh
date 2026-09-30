#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Keep the requested filename. Online mode synchronizes public release history;
# --offline uses only local tags and cannot check unpublished local metadata
# against registry history. Neither mode pushes tags or container images.
offline=false
case "${1:-}" in
    '') ;;
    --offline) offline=true; shift ;;
    --help|-h)
        echo 'Usage: ./create_realease.sh [--offline]'
        echo 'Verify release history, create the semrel release tag, then run build.sh.'
        exit 0
        ;;
    *) echo 'Error: unknown option. Use --help.' >&2; exit 2 ;;
esac
(( $# == 0 )) || { echo 'Error: unexpected arguments.' >&2; exit 2; }

fail() { echo "Error: $*" >&2; exit 2; }
[[ -z $(git status --porcelain --untracked-files=normal) ]] \
    || fail 'Commit or remove local changes before creating a release.'
[[ $(git rev-parse --is-shallow-repository) == false ]] \
    || fail 'Release creation requires full Git history.'
revision=$(git rev-parse HEAD)

# Serialize release creation within this checkout, with temporary state outside
# the project. Existing Git tags are never moved, including fetched conflicts.
mkdir -p "${TMPDIR:-/tmp/bonsai27}"
checkout_key=$(printf '%s' "$PWD" | sha256sum)
checkout_key=${checkout_key%% *}
exec 9>"${TMPDIR:-/tmp/bonsai27}/release-$checkout_key.lock"
flock 9
if [[ "$offline" == false ]]; then
    # Public HTTPS also works when the configured SSH remote has no local key.
    git fetch --tags https://github.com/TeaAlc/ai_bonsai27.git
    published=$(python3 -B tools/published-release.py)
    if [[ -n "$published" ]]; then
        read -r published_version published_revision <<< "$published"
        git cat-file -e "$published_revision^{commit}" \
            || fail 'Published source commit is missing; update this checkout.'
        git merge-base --is-ancestor "$published_revision" "$revision" \
            || fail 'Published release is not an ancestor of this checkout.'
        published_tag="v$published_version"
        if git show-ref --verify --quiet "refs/tags/$published_version"; then
            [[ $(git rev-parse "$published_version^{commit}") == "$published_revision" ]] \
                || fail "$published_version conflicts with the published image."
        fi
        if git show-ref --verify --quiet "refs/tags/$published_tag"; then
            [[ $(git rev-parse "$published_tag^{commit}") == "$published_revision" ]] \
                || fail "$published_tag conflicts with the published image; resolve the release history explicitly."
        else
            git tag -a "$published_tag" "$published_revision" \
                -m "Release $published_version (by Codex)"
            echo "Restored missing release baseline: $published_tag at $published_revision"
        fi
    fi
else
    echo 'Offline mode: published tags and registry metadata are not checked.'
fi

# semrel alone determines the next version. No artificial bump or parallel
# commit parser is used. A docs-only update cannot replace an existing release.
version=$(./tools/version.sh)
tag="v$version"
created_tag=false
if git show-ref --verify --quiet "refs/tags/$version"; then
    [[ $(git rev-parse "$version^{commit}") == "$revision" ]] \
        || fail "$version already exists at another commit; no new releasable change was found."
fi
if git show-ref --verify --quiet "refs/tags/$tag"; then
    [[ $(git rev-parse "$tag^{commit}") == "$revision" ]] \
        || fail "$tag already exists at another commit; no new releasable change was found."
else
    git tag -a "$tag" "$revision" -m "Release $version (by Codex)"
    created_tag=true
fi

# Remove only this newly created release tag if the build fails. A recovered
# published baseline remains valid. Pre-existing tags are never deleted.
cleanup() {
    local status=$?
    if (( status != 0 )) && [[ "$created_tag" == true ]]; then
        if [[ $(git rev-parse "$tag^{commit}") == "$revision" ]]; then
            git tag -d "$tag" >&2
        fi
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ $(git rev-parse HEAD) == "$revision" ]] || fail 'HEAD changed during release creation.'
echo "Creating release $version from $revision; Git and GHCR publication remain separate."

# Tagging establishes the same version as the build baseline. This final action
# builds both the versioned image and latest through the existing build script.
./build.sh
