#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

source tools/project.sh
lock_project

# Release the image's actual source commit, not a newer checkout. Inspect the
# last local build; pushing tags and images remains an explicit separate step.
image=${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}
metadata=$(podman image inspect --format \
    '{{index .Config.Labels "org.opencontainers.image.version"}} {{index .Config.Labels "org.opencontainers.image.revision"}} {{index .Config.Labels "io.bonsai.git.dirty"}} {{index .Config.Labels "org.opencontainers.image.source"}}' "$image")
read -r version revision dirty source <<< "$metadata"
[[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] \
    || { echo 'Error: image has no valid release version.' >&2; exit 2; }
[[ "$revision" =~ ^[0-9a-f]{40}$ && "$dirty" == false ]] \
    || { echo 'Error: release requires a clean, committed image build.' >&2; exit 2; }
[[ "$source" == https://github.com/TeaAlc/ai_bonsai27 ]] \
    || { echo 'Error: image belongs to a different project.' >&2; exit 2; }
git cat-file -e "$revision^{commit}"
assert_tag_aliases "$version" "$revision"
tag="v$version"

# Never move an existing release tag. Repeated tagging of the same build is OK.
if git show-ref --verify --quiet "refs/tags/$tag"; then
    [[ $(git rev-parse "$tag^{commit}") == "$revision" ]] \
        || { echo "Error: $tag already identifies a different commit." >&2; exit 2; }
    echo "Release tag $tag already identifies $revision"
else
    git tag -a "$tag" "$revision" -m "Release $version (by Codex)"
    echo "Created release tag $tag at image source $revision"
fi
