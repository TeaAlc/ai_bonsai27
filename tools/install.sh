#!/usr/bin/env bash
set -euo pipefail

tools_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$tools_dir/semrel/artifacts.sh"
binary="$tools_dir/semrel/bin/semrel"
archive="$tools_dir/semrel/downloads/semrel-$SEMREL_TOOL_VERSION-linux-x86_64.tar.gz"

# Linux and WSL2 on x86-64 use the same standalone binary; no global install,
# Go toolchain, or Node packages are needed.
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
    echo 'The pinned build tool supports x86-64 Linux and WSL2.' >&2
    exit 2
fi

checksum_matches() {
    local file=$1 expected=$2
    [[ -f "$file" ]] && printf '%s  %s\n' "$expected" "$file" | sha256sum --status -c -
}

# A verified cached binary makes subsequent builds independent of the network.
if [[ -x "$binary" ]] && checksum_matches "$binary" "$SEMREL_BINARY_SHA256"; then
    exit 0
fi

mkdir -p "$tools_dir/semrel/bin" "$tools_dir/semrel/downloads" "${TMPDIR:-/tmp/bonsai27}"
staging=$(mktemp -d "${TMPDIR:-/tmp/bonsai27}/semrel-install.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT

if ! checksum_matches "$archive" "$SEMREL_ARCHIVE_SHA256"; then
    echo "Downloading semrel $SEMREL_TOOL_VERSION into tools/semrel/" >&2
    curl -fL --retry 4 "$SEMREL_ARCHIVE_URL" -o "$staging/archive.tar.gz"
    printf '%s  %s\n' "$SEMREL_ARCHIVE_SHA256" "$staging/archive.tar.gz" | sha256sum -c - >&2
    mv -- "$staging/archive.tar.gz" "$archive"
fi

# Extract only the required executable, then verify it before installing it.
tar -xzf "$archive" -C "$staging" semrel
printf '%s  %s\n' "$SEMREL_BINARY_SHA256" "$staging/semrel" | sha256sum -c - >&2
chmod 755 "$staging/semrel"
mv -- "$staging/semrel" "$binary"
