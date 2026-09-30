#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/data/models/download.sh"

# Small fixtures exercise the real locking, checksum, and atomic rename logic
# without downloading multi-gigabyte models. Only the HTTP transfer is mocked.
mkdir -p /tmp/bonsai27
work_dir=$(mktemp -d /tmp/bonsai27/model-test.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT
printf 'model fixture\n' > "$work_dir/source"
expected_sha=$(sha256sum "$work_dir/source")
expected_sha=${expected_sha%% *}
export fixture_source="$work_dir/source" fixture_calls="$work_dir/calls"
mkdir "$work_dir/bin"
# Simulate the reported filesystem failure. Downloads must not invoke flock.
cat > "$work_dir/bin/flock" <<'SH'
#!/usr/bin/env bash
echo 'flock: 9: Function not implemented' >&2
exit 1
SH
cat > "$work_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo called >> "$fixture_calls"
while (( $# )); do
    if [[ "$1" == --output ]]; then
        cp "$fixture_source" "$2"
        exit 0
    fi
    shift
done
exit 2
SH
chmod +x "$work_dir/bin/curl" "$work_dir/bin/flock"
export PATH="$work_dir/bin:$PATH"

destination="$work_dir/cache/model.gguf"
download_missing_model fixture "$destination" "$expected_sha"
cmp "$fixture_source" "$destination"
[[ ! -e "$destination.part" ]]
[[ ! -d "$destination.lock.d" ]]
download_missing_model fixture "$destination" "$expected_sha"
[[ $(wc -l < "$fixture_calls") == 1 ]]

# Failed integrity checks must not publish an invalid model or leave bad data.
if download_missing_model fixture "$work_dir/bad.gguf" "${expected_sha//?/0}"; then
    echo 'Error: invalid checksum was accepted.' >&2
    exit 1
fi
[[ ! -e "$work_dir/bad.gguf" && ! -e "$work_dir/bad.gguf.part" ]]
[[ ! -d "$work_dir/bad.gguf.lock.d" ]]

# Concurrent starts must share a single completed download.
download_missing_model fixture "$work_dir/shared.gguf" "$expected_sha" &
first_pid=$!
download_missing_model fixture "$work_dir/shared.gguf" "$expected_sha" &
second_pid=$!
wait "$first_pid"
wait "$second_pid"
[[ $(wc -l < "$fixture_calls") == 3 ]]
cmp "$fixture_source" "$work_dir/shared.gguf"
[[ ! -d "$work_dir/shared.gguf.lock.d" ]]

# An existing lock must prevent transfer until its owner releases it.
mkdir "$work_dir/wait.gguf.lock.d"
(sleep 1; rmdir "$work_dir/wait.gguf.lock.d") &
lock_owner=$!
download_missing_model fixture "$work_dir/wait.gguf" "$expected_sha"
wait "$lock_owner"
[[ $(wc -l < "$fixture_calls") == 4 ]]

# Host downloads must find an existing cache relative to the caller's directory.
mkdir "$work_dir/existing"
printf cached > "$work_dir/existing/$MODEL_FILE"
printf cached > "$work_dir/existing/$VISION_FILE"
(cd "$work_dir/existing" && "$repo_dir/download_models.sh")
(cd "$work_dir" && BONSAI_MODEL_DIR=existing "$repo_dir/download_models.sh")
[[ $(wc -l < "$fixture_calls") == 4 ]]
echo 'Passed model download, reuse, integrity, concurrency, and directory checks.'
