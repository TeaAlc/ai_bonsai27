#!/usr/bin/env bash
# Each repetition gets a new server and empty prompt cache.
set -euo pipefail
model_dir=$(realpath -m -- "${BONSAI_MODEL_DIR:-$PWD}")
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$project_dir"
source data/gpu/settings.sh
if (( $# < 2 )); then
    echo 'Usage: benchmark-backends.sh <label> <local-image> [repetitions:3] [server-options...]' >&2
    exit 2
fi
[[ "$1" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Error: use letters, digits, underscores, and hyphens for the label.' >&2; exit 2; }
port=${BONSAI_PORT:-18084}
validate_decimal BONSAI_PORT "$port" 1 65535
port=$((10#$port))
export BONSAI_CTX_SIZE=16384
export BONSAI_REASONING_EFFORT=medium
validate_bonsai_settings
mkdir -p /tmp/bonsai27
work=$(mktemp -d /tmp/bonsai27/backend-benchmark.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
gpu_args=(--device nvidia.com/gpu=all)
if [[ -e /dev/dxg ]]; then
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
fi
label=$1
image=$2
repetitions=${3:-3}
validate_decimal repetitions "$repetitions" 1 10
repetitions=$((10#$repetitions))
[[ -n "$image" && "$image" != -* && "$image" != *[[:space:]]* ]] || { echo 'Error: expected a local image reference.' >&2; exit 2; }
podman image exists "$image"
if (( $# >= 3 )); then shift 3; else shift 2; fi
# Extract the tested image's entrypoint, preserving all GPU/context/vision flags.
# Replacing the strategy prevents accidentally appending DFlash alongside MTP.
draft_model=${BONSAI_EXPERIMENT_DRAFT_MODEL:-}
if [[ -n "$draft_model" ]]; then
    draft_model=$(realpath -- "$draft_model")
    [[ -r "$draft_model" && -s "$draft_model" ]] || { echo 'Error: draft model must be a readable nonempty file.' >&2; exit 2; }
    draft_pdl=${BONSAI_EXPERIMENT_PDL:-1}
    case "$draft_pdl" in
        0|1) ;;
        *) echo 'Error: BONSAI_EXPERIMENT_PDL must be 0 or 1.' >&2; exit 2 ;;
    esac
    draft_depth=${BONSAI_EXPERIMENT_DRAFT_N_MAX:-3}
    validate_decimal BONSAI_EXPERIMENT_DRAFT_N_MAX "$draft_depth" 1 15
    draft_depth=$((10#$draft_depth))
    podman run --rm --pull=never --entrypoint cat "$image" /usr/local/bin/bonsai-server > "$work/entrypoint.sh"
    python3 -B - "$work/entrypoint.sh" "$draft_depth" <<'PYDRAFT'
import sys
sys.dont_write_bytecode = True
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
assert text.count('--spec-type draft-mtp') == 1, 'Unsupported image entrypoint: expected one MTP strategy.'
assert text.count('--spec-draft-n-max 2') == 1, 'Unsupported image entrypoint: expected MTP depth 2.'
draft_options = (f'--spec-draft-n-max {sys.argv[2]}\n'
                 '    --spec-draft-model /draft/model.gguf\n'
                 "    --spec-draft-override-tensor '.*=CUDA0'")
text = text.replace('--spec-type draft-mtp', '--spec-type draft-dflash')
text = text.replace('--spec-draft-n-max 2', draft_options)
text = text.replace('MTP=2;', f'DFlash draft={sys.argv[2]};')
path.write_text(text)
PYDRAFT
fi
root=${BONSAI_TEST_RUN_DIR:-"$PWD/results/backend-benchmarks/$(date -u +%Y%m%dT%H%M%SZ)-$label-$$"}
mkdir -p "$root"
name="bonsai-backend-benchmark-$$"
monitor_pid=
nvidia_smi=$(command -v nvidia-smi || true)
if [[ -z "$nvidia_smi" && -x /usr/lib/wsl/lib/nvidia-smi ]]; then
    nvidia_smi=/usr/lib/wsl/lib/nvidia-smi
fi
stop_monitor() {
    if [[ -n "$monitor_pid" ]]; then
        kill "$monitor_pid" 2>/dev/null || true
        wait "$monitor_pid" 2>/dev/null || true
        monitor_pid=
    fi
}
cleanup() {
    stop_monitor
    if podman container exists "$name"; then
        podman logs "$name" > "$root/last-container.log" 2>&1 || true
        podman rm -f "$name" >/dev/null 2>&1 || true
    fi
}
finish() {
    local status=$?
    cleanup
    rm -rf -- "$work"
    if (( status != 0 )); then
        printf 'Error: benchmark stopped (exit %s); preserved evidence: %s\n' "$status" "$root" >&2
    fi
    return "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for ((repeat=1; repeat<=repetitions; repeat++)); do
    cleanup
    # Keep timestamped global GPU telemetry, including startup and inference.
    # It exposes competing load; it does not attribute VRAM to this container.
    if [[ -n "$nvidia_smi" ]]; then
        "$nvidia_smi" --query-gpu=timestamp,name,memory.used,utilization.gpu,power.draw,temperature.gpu \
            --format=csv --loop=1 > "$root/gpu-monitor-$repeat.csv" 2>&1 &
        monitor_pid=$!
    fi
    if [[ -n "$draft_model" ]]; then
        podman run -d --pull=never --name "$name" "${gpu_args[@]}" \
            --security-opt label=disable \
            -p "127.0.0.1:$port:8080" \
            -v "$model_dir:/models:rw" \
            -v "$draft_model:/draft/model.gguf:ro" \
            -v "$work/entrypoint.sh:/experiment-entrypoint.sh:ro" \
            -e BONSAI_CTX_SIZE=16384 -e BONSAI_REASONING_EFFORT=medium \
            -e "BONSAI_GPU_BACKEND=${BONSAI_GPU_BACKEND:-}" \
            -e "GGML_CUDA_PDL=$draft_pdl" \
            --entrypoint bash "$image" /experiment-entrypoint.sh "$@"
    else
        BONSAI_IMAGE="$image" BONSAI_CONTAINER_NAME="$name" BONSAI_PORT="$port" \
            BONSAI_MODEL_DIR="$model_dir" ./run.sh "$@"
    fi
    python3 -B - "$name" "$port" <<'PY'
import sys
sys.dont_write_bytecode = True
import subprocess
import time
import urllib.request
for attempt in range(180):
    try:
        with urllib.request.urlopen('http://127.0.0.1:'+sys.argv[2]+'/health',timeout=2) as r:
            if r.status == 200:
                break
    except Exception:
        pass
    status = subprocess.check_output(
        ['podman', 'inspect', '--format', '{{.State.Status}}', sys.argv[1]], text=True).strip()
    if status != 'running':
        raise SystemExit('Container exited during startup: ' + status)
    time.sleep(1)
else:
    raise SystemExit('Readiness timeout')
PY
    podman exec "$name" readlink /proc/1/exe > "$root/executable-$repeat.txt"
    podman inspect "$name" > "$root/container-$repeat.json"
    if [[ -n "$nvidia_smi" ]]; then
        "$nvidia_smi" --query-gpu=name,memory.used,utilization.gpu,power.draw,temperature.gpu --format=csv > "$root/gpu-$repeat.csv"
    fi
    timeout --signal=INT --kill-after=10s 120s env BONSAI_BENCHMARK_RESULT="$root/benchmark-$repeat.json" ./simple_text_benchmark.sh "127.0.0.1:$port"
    stop_monitor
    podman logs "$name" > "$root/server-$repeat.log" 2>&1
    if ((repeat==repetitions)); then
        BONSAI_BASE_URL="http://127.0.0.1:$port" BONSAI_TEST_CONTAINER="$name" \
            BONSAI_TEST_SUITE_ID="backend-$label" BONSAI_TEST_RUN_DIR="$root/quality" \
            timeout --signal=INT --kill-after=10s 90s python3 -B tests/test-quality.py
        if [[ ${BONSAI_EXPERIMENT_CODING:-0} == 1 ]]; then
            BONSAI_BASE_URL="http://127.0.0.1:$port" BONSAI_TEST_CONTAINER="$name" \
                BONSAI_TEST_SUITE_ID="backend-$label" BONSAI_TEST_RUN_DIR="$root/quality" \
                timeout --signal=INT --kill-after=10s 120s python3 -B tests/test-coding.py
        fi
    fi
done

printf 'Benchmark evidence: %s\n' "$root"
