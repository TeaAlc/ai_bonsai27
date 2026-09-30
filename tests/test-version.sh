#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
version_tool="$project_dir/tools/version.sh"
mkdir -p "${TMPDIR:-/tmp/bonsai27}"
fixtures=$(mktemp -d "${TMPDIR:-/tmp/bonsai27}/version-tests.XXXXXX")
trap 'rm -rf -- "$fixtures"' EXIT

# Each fixture is isolated from the real repository and needs no remote access.
new_repository() {
    repository="$fixtures/$1"
    git init --quiet --initial-branch=main "$repository"
    git -C "$repository" config user.name 'Version Test'
    git -C "$repository" config user.email 'version-test@example.invalid'
    git -C "$repository" commit --quiet --allow-empty -m 'feat: initial feature'
}

expect_version() {
    local expected=$1 actual
    local tags_before head_before
    tags_before=$(git -C "$repository" show-ref --tags || true)
    head_before=$(git -C "$repository" rev-parse HEAD)
    actual=$("$version_tool" "$repository")
    if [[ "$actual" != "$expected" ]]; then
        echo "Expected $expected, got $actual in $repository" >&2
        exit 1
    fi
    [[ $(git -C "$repository" show-ref --tags || true) == "$tags_before" ]]
    [[ $(git -C "$repository" rev-parse HEAD) == "$head_before" ]]
    echo "PASS: $(basename -- "$repository") -> $actual (original refs unchanged)"
}

new_repository first-build
expect_version 1.0.0

new_repository lightweight-tag
git -C "$repository" tag v1.2.3
expect_version 1.2.3
git -C "$repository" commit --quiet --allow-empty -m 'docs: clarify setup'
expect_version 1.2.3
git -C "$repository" commit --quiet --allow-empty -m 'fix: correct configuration'
expect_version 1.2.4

new_repository annotated-tag
git -C "$repository" tag -a v1.2.3 -m 'Release 1.2.3'
git -C "$repository" commit --quiet --allow-empty -m 'perf: improve startup'
expect_version 1.2.4

new_repository feature
git -C "$repository" tag v1.2.3
git -C "$repository" commit --quiet --allow-empty -m 'feat: add configuration'
expect_version 1.3.0

# A feature after the existing 1.1.0 release must produce the requested 1.2.0.
new_repository release-1.2.0
git -C "$repository" tag -a v1.1.0 -m 'Release 1.1.0'
git -C "$repository" commit --quiet --allow-empty -m 'feat(build): add image-based release tagging'
expect_version 1.2.0
git -C "$repository" commit --quiet --allow-empty -m 'docs: explain release workflow'
expect_version 1.2.0

new_repository breaking-subject
git -C "$repository" tag v1.2.3
git -C "$repository" commit --quiet --allow-empty -m 'feat!: change API'
expect_version 2.0.0

new_repository breaking-footer
git -C "$repository" tag v1.2.3
git -C "$repository" commit --quiet --allow-empty \
    -m 'fix: change defaults' -m 'BREAKING CHANGE: the old defaults were removed'
expect_version 2.0.0

new_repository unrelated-tag
git -C "$repository" tag -a v1.2.3 -m 'Release 1.2.3'
git -C "$repository" checkout --quiet -b other
git -C "$repository" commit --quiet --allow-empty -m 'feat: unrelated release'
git -C "$repository" tag v9.0.0
git -C "$repository" checkout --quiet main
git -C "$repository" commit --quiet --allow-empty -m 'fix: main branch change'
expect_version 1.2.4

# Shallow history must fail instead of silently returning a misleading version.
git clone --quiet --depth 1 "file://$repository" "$fixtures/shallow"
if "$version_tool" "$fixtures/shallow" > "$fixtures/shallow-output" 2>&1; then
    echo 'A shallow checkout unexpectedly passed version calculation' >&2
    exit 1
fi
echo 'PASS: shallow checkout rejected'

new_repository contradictory-aliases
git -C "$repository" tag 1.2.3
git -C "$repository" commit --quiet --allow-empty -m 'fix: later source'
git -C "$repository" tag v1.2.3
if "$version_tool" "$repository"; then exit 1; fi
echo 'PASS: contradictory tag aliases rejected'
