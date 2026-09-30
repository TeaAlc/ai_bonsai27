#!/usr/bin/env bash
# Serialize preparation, builds, tagging, and publication within this checkout.
# This lock is local temporary state; model caches use separate directory locks.
lock_project() {
    local key lock_path
    mkdir -p "${TMPDIR:-/tmp/bonsai27}"
    key=$(printf '%s' "$PWD" | sha256sum)
    lock_path="${TMPDIR:-/tmp/bonsai27}/project-${key%% *}.lock"
    if [[ ${BONSAI_PROJECT_LOCK:-} == "$lock_path" && -e /proc/self/fd/9 && $(readlink /proc/self/fd/9) == "$lock_path" ]]; then
        return
    fi
    exec 9>"$lock_path"
    flock -w 600 9 || { echo 'Error: timed out waiting for another project operation.' >&2; return 2; }
    export BONSAI_PROJECT_LOCK="$lock_path"
}

assert_tag_aliases() {
    local version=$1 revision=$2 tag
    for tag in "$version" "v$version"; do
        if git show-ref --verify --quiet "refs/tags/$tag"; then
            [[ $(git rev-parse "$tag^{commit}") == "$revision" ]] \
                || { echo "Error: $tag identifies a different source commit." >&2; return 2; }
        fi
    done
}
