#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
mkdir -p /tmp/bonsai27
work=$(mktemp -d /tmp/bonsai27/container-download.XXXXXX)
container="bonsai-download-test-$$"
cleanup() {
    podman rm --force "$container" >/dev/null 2>&1 || true
    rm -rf -- "$work"
}
trap cleanup EXIT
image=${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}
mkdir "$work/models"
# Only the transfer is replaced. The image's real PID 1, CUDA preflight,
# model helper, shared-cache directory lock, and signal forwarding remain active.
cat > "$work/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
while (( $# )); do
    if [[ "$1" == --output ]]; then
        printf partial > "$2"
        printf started > /models/transfer-started
        exec sleep 300
    fi
    shift
done
exit 2
SH
chmod +x "$work/curl"
if [[ -e /dev/dxg ]]; then
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
else
    gpu_args=(--device nvidia.com/gpu=all)
fi
podman run -d --name "$container" "${gpu_args[@]}" \
    -v "$work/models:/models:rw" -v "$work/curl:/usr/local/bin/curl:ro" \
    --security-opt label=disable "$image" >/dev/null
for ((attempt=0;attempt<100;attempt++)); do
    [[ ! -e "$work/models/transfer-started" ]] || break
    sleep .1
done
[[ -e "$work/models/transfer-started" ]] || { podman logs "$container"; exit 1; }
podman stop --time 5 "$container" >/dev/null
exit_code=$(podman inspect --format '{{.State.ExitCode}}' "$container")
[[ "$exit_code" == 143 ]] || { echo "Error: stop required forced kill (exit $exit_code)." >&2; exit 1; }
[[ ! -d "$work/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf.lock.d" ]]
[[ -s "$work/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf.part" ]]
podman rm "$container" >/dev/null
# A read-only cache must fail before any transfer, with a bounded diagnostic.
mkdir "$work/read-only"
if podman run --rm "${gpu_args[@]}" --security-opt label=disable \
    -v "$work/read-only:/models:ro" -v "$work/curl:/usr/local/bin/curl:ro" \
    "$image" > "$work/read-only.log" 2>&1; then exit 1; fi
[[ $(< "$work/read-only.log") == *'Check write access'* ]]
[[ -z $(ls -A "$work/read-only") ]]
echo 'Passed real PID 1 stop, child cancellation, lock cleanup, retained partial, and read-only cache checks.'
