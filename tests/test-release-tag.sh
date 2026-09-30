#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p /tmp/bonsai27
work_dir=$(mktemp -d /tmp/bonsai27/release-tag-test.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT
mkdir -p "$work_dir/repo/tools" "$work_dir/bin"
cp "$project_dir/tools/tag-release.sh" "$work_dir/repo/tools/"
git -C "$work_dir/repo" init --quiet --initial-branch=main
git -C "$work_dir/repo" config user.name 'Release Test'
git -C "$work_dir/repo" config user.email 'release-test@example.invalid'
git -C "$work_dir/repo" add tools
git -C "$work_dir/repo" commit --quiet -m 'feat: initial release'
source_revision=$(git -C "$work_dir/repo" rev-parse HEAD)
git -C "$work_dir/repo" commit --quiet --allow-empty -m 'docs: newer checkout'

# Only image inspection is mocked; the helper creates real isolated Git tags.
cat > "$work_dir/bin/podman" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$fixture_metadata"
SH
chmod +x "$work_dir/bin/podman"
export PATH="$work_dir/bin:$PATH"
export fixture_metadata="1.2.0 $source_revision false"
helper="$work_dir/repo/tools/tag-release.sh"
"$helper"
[[ $(git -C "$work_dir/repo" rev-parse 'v1.2.0^{commit}') == "$source_revision" ]]
tag_object=$(git -C "$work_dir/repo" rev-parse v1.2.0)
"$helper"
[[ $(git -C "$work_dir/repo" rev-parse v1.2.0) == "$tag_object" ]]

fixture_metadata="1.2.0 $(git -C "$work_dir/repo" rev-parse HEAD) false"
if "$helper"; then exit 1; fi
fixture_metadata="1.3.0 $source_revision true"
if "$helper"; then exit 1; fi
fixture_metadata="invalid $source_revision false"
if "$helper"; then exit 1; fi
[[ $(git -C "$work_dir/repo" rev-parse v1.2.0) == "$tag_object" ]]
[[ $(git -C "$work_dir/repo" tag --list) == v1.2.0 ]]
echo 'Passed source revision, idempotence, conflict, dirty build, and version checks.'
