#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p /tmp/bonsai27
work_dir=$(mktemp -d /tmp/bonsai27/create-release-test.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT
export fixture_version_tool="$project_dir/tools/version.sh"
export fixture_events="$work_dir/build.log"
export fixture_build_fail=false

# Use real Git and real semrel in isolated repositories; mock only the build.
new_repository() {
    repository="$work_dir/$1"
    mkdir -p "$repository/tools"
    mkdir -p "$repository/data"
    cp "$project_dir/data/logging.sh" "$repository/data/"
    cp "$project_dir/create_realease.sh" "$repository/"
    cp "$project_dir/tools/project.sh" "$repository/tools/"
    cat > "$repository/tools/version.sh" <<'SH'
#!/usr/bin/env bash
exec "$fixture_version_tool" "$(dirname -- "${BASH_SOURCE[0]}")/.."
SH
    cat > "$repository/image_build.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
version=$(./tools/version.sh)
[[ $(git rev-parse "v$version^{commit}") == $(git rev-parse HEAD) ]]
echo "$version" >> "$fixture_events"
[[ "$fixture_build_fail" == false ]]
SH
    chmod +x "$repository/tools/version.sh" "$repository/image_build.sh"
    git -C "$repository" init --quiet --initial-branch=main
    git -C "$repository" config user.name 'Release Test'
    git -C "$repository" config user.email 'release-test@example.invalid'
    git -C "$repository" add .
    git -C "$repository" commit --quiet -m 'feat: initial release'
}

new_repository minor
git -C "$repository" tag v1.2.0
git -C "$repository" commit --quiet --allow-empty -m 'feat: add automatic releases'
"$repository/create_realease.sh" --offline
[[ $(git -C "$repository" rev-parse 'v1.3.0^{commit}') == $(git -C "$repository" rev-parse HEAD) ]]
[[ $(tail -n 1 "$fixture_events") == 1.3.0 ]]
"$repository/create_realease.sh" --offline
git -C "$repository" commit --quiet --allow-empty -m 'docs: explain releases'
if "$repository/create_realease.sh" --offline; then exit 1; fi

new_repository patch
git -C "$repository" tag v1.2.0
git -C "$repository" commit --quiet --allow-empty -m 'fix: validate CUDA access'
"$repository/create_realease.sh" --offline
[[ $(tail -n 1 "$fixture_events") == 1.2.1 ]]

new_repository failed-build
git -C "$repository" tag v1.2.0
git -C "$repository" commit --quiet --allow-empty -m 'fix: repair startup'
fixture_build_fail=true
if "$repository/create_realease.sh" --offline; then exit 1; fi
[[ $(git -C "$repository" tag --list) == v1.2.0 ]]
fixture_build_fail=false

new_repository dirty
echo uncommitted > "$repository/local-change"
if "$repository/create_realease.sh" --offline; then exit 1; fi
[[ -z $(git -C "$repository" tag --list) ]]

# Mock public metadata/fetch to exercise recovery of a missing published tag.
new_repository recovered-baseline
published_revision=$(git -C "$repository" rev-parse HEAD)
git -C "$repository" commit --quiet --allow-empty -m 'fix: after published image'
mkdir "$work_dir/bin"
export fixture_real_git
fixture_real_git=$(command -v git)
export fixture_published_revision="$published_revision"
cat > "$work_dir/bin/git" <<'SH'
#!/usr/bin/env bash
if [[ "${1:-}" == fetch ]]; then exit 0; fi
exec "$fixture_real_git" "$@"
SH
cat > "$work_dir/bin/python3" <<'SH'
#!/usr/bin/env bash
printf '1.2.0 %s\n' "$fixture_published_revision"
SH
chmod +x "$work_dir/bin/"*
PATH="$work_dir/bin:$PATH" "$repository/create_realease.sh"
[[ $(git -C "$repository" rev-parse 'v1.2.0^{commit}') == "$published_revision" ]]
[[ $(tail -n 1 "$fixture_events") == 1.2.1 ]]

# A tag pointing at the wrong published source must fail without moving it.
new_repository conflicting-baseline
fixture_published_revision=$(git -C "$repository" rev-parse HEAD)
git -C "$repository" commit --quiet --allow-empty -m 'fix: newer checkout'
git -C "$repository" tag v1.2.0
conflicting_tag=$(git -C "$repository" rev-parse v1.2.0)
if PATH="$work_dir/bin:$PATH" "$repository/create_realease.sh"; then exit 1; fi
[[ $(git -C "$repository" rev-parse v1.2.0) == "$conflicting_tag" ]]
echo 'Passed semrel bumps, repeat release, docs-only rejection, rollback, dirty checkout, and published baseline recovery.'

# Parallel calls share the checkout lock and retain one stable release source.
new_repository concurrent-release
git -C "$repository" tag v1.2.0
git -C "$repository" commit --quiet --allow-empty -m 'fix: concurrent fixture'
"$repository/create_realease.sh" --offline &
first=$!
"$repository/create_realease.sh" --offline &
second=$!
wait "$first"
wait "$second"
[[ $(git -C "$repository" rev-parse 'v1.2.1^{commit}') == $(git -C "$repository" rev-parse HEAD) ]]
echo 'Passed concurrent release creation without moving tags.'
