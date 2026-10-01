#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
mkdir -p /tmp/bonsai27
work=$(mktemp -d /tmp/bonsai27/run-image-test.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/bin" "$work/models"

# Mock only the container engine; exercise the real startup script and stdin.
cat > "$work/bin/podman" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >> "$RUN_TEST_TRACE"
case "$1" in
    image) exit "${RUN_TEST_EXISTS:-0}" ;;
    pull) exit "${RUN_TEST_PULL:-0}" ;;
    run) printf 'fixture-container-id\n' ;;
    *) exit 99 ;;
esac
MOCK
chmod +x "$work/bin/podman"
export PATH="$work/bin:$PATH" BONSAI_MODEL_DIR="$work/models"
export RUN_TEST_TRACE="$work/trace"
unset BONSAI_IMAGE

run_case() {
    local expected=$1 input=$2
    : > "$RUN_TEST_TRACE"
    local status=0
    bash ./run.sh --log-verbose <<< "$input" > "$work/out" 2> "$work/err" || status=$?
    [[ "$status" == "$expected" ]]
}

# Cached images start without prompting or pulling and preserve server arguments.
export RUN_TEST_EXISTS=0
run_case 0 ''
! rg -q '^pull$' "$RUN_TEST_TRACE"
! rg -q 'Remote image to download' "$work/err"
rg -q '^--pull=never$' "$RUN_TEST_TRACE"
rg -q '^--log-verbose$' "$RUN_TEST_TRACE"

# Enter accepts GHCR, while a supplied address selects another registry/tag.
export RUN_TEST_EXISTS=1
run_case 0 ''
rg -q 'Remote image to download \[ghcr.io/teaalc/ai_bonsai27:latest\]' "$work/err"
[[ $(rg -c '^ghcr.io/teaalc/ai_bonsai27:latest$' "$RUN_TEST_TRACE") == 2 ]]
run_case 0 'registry.example.org/team/bonsai:2.0.0'
[[ $(rg -c '^registry.example.org/team/bonsai:2.0.0$' "$RUN_TEST_TRACE") == 2 ]]

# A failed pull must prevent creation; engine failures must not trigger a pull.
export RUN_TEST_PULL=17
run_case 17 ''
! rg -q '^run$' "$RUN_TEST_TRACE"
rg -q '\[image-download\].*exit=17' "$work/err"
unset RUN_TEST_PULL
export RUN_TEST_EXISTS=125
run_case 125 ''
! rg -q '^pull$|^run$' "$RUN_TEST_TRACE"

# EOF and malformed references cannot authorize or initiate a download.
export RUN_TEST_EXISTS=1
: > "$RUN_TEST_TRACE"
status=0
bash ./run.sh < /dev/null > "$work/out" 2> "$work/err" || status=$?
[[ "$status" == 2 ]]
! rg -q '^pull$|^run$' "$RUN_TEST_TRACE"
for invalid in '--all-tags' 'registry.example.org/image extra'; do
    run_case 2 "$invalid"
    ! rg -q '^pull$|^run$' "$RUN_TEST_TRACE"
done

echo 'Passed local image selection, confirmed remote pulls, argument forwarding, and failure handling.'
