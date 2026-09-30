#!/usr/bin/env bash
set -euo pipefail

tools_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repository=${1:-$(dirname -- "$tools_dir")}
repository=$(git -C "$repository" rev-parse --show-toplevel)

# Incomplete history can produce an incorrect release version. The caller must
# explicitly obtain full history and tags before building a shallow checkout.
if [[ $(git -C "$repository" rev-parse --is-shallow-repository) == true ]]; then
    echo 'Version calculation needs a full Git checkout, including release tags.' >&2
    exit 2
fi
revision=$(git -C "$repository" rev-parse HEAD)
"$tools_dir/install.sh"

# semrel 0.7.0 compares tag object hashes to commit hashes. Use an isolated,
# local snapshot and dereference annotated tags there. This also limits
# release baselines to stable SemVer tags reachable from the selected HEAD.
# Original refs, files, and remotes are never changed by version calculation.
mkdir -p "${TMPDIR:-/tmp/bonsai27}"
snapshot=$(mktemp -d "${TMPDIR:-/tmp/bonsai27}/semrel-version.XXXXXX")
trap 'rm -rf -- "$snapshot"' EXIT
git clone --quiet --no-hardlinks --no-checkout "$repository" "$snapshot"
git -C "$snapshot" update-ref HEAD "$revision"

while IFS= read -r tag; do
    if [[ "$tag" =~ ^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
        tagged_commit=$(git -C "$repository" rev-parse "refs/tags/$tag^{commit}")
        if git -C "$repository" merge-base --is-ancestor "$tagged_commit" "$revision"; then
            git -C "$snapshot" update-ref "refs/tags/$tag" "$tagged_commit"
            continue
        fi
    fi
    git -C "$snapshot" update-ref -d "refs/tags/$tag"
done < <(git -C "$snapshot" tag --list)

# Keep all release policy beside the tool and explicitly disable tagging/pushing.
cp -- "$tools_dir/semrel/config.yaml" "$snapshot/.semrel.yaml"
version=$(cd "$snapshot" && "$tools_dir/semrel/bin/semrel" --current-branch-only)
if [[ ! "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "semrel returned an invalid stable version: $version" >&2
    exit 2
fi
printf '%s\n' "$version"
