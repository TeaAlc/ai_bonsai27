#!/usr/bin/env bash
# Shared, pinned model artifacts for host preparation and container startup.
readonly VISION_REVISION=b072e1d3b35a0a630cece372c2127528e0994386
readonly BACKEND_REPO=https://huggingface.co/sudoingx/Ternary-Bonsai-2-27B-PTQ1_0-MTP-GGUF/resolve/f04a3bd22b7b482675663e99efaba6719347b419
# An explicit PQ2_0 image uses the equivalent unmodified Bonsai body with MTP.
# Keep bundle downloads independent of the selected language-model repository.
case "${BONSAI_MODEL_VARIANT:-ptq1_0}" in
    ptq1_0)
        readonly MODEL_REVISION=f04a3bd22b7b482675663e99efaba6719347b419
        readonly MODEL_REPO=$BACKEND_REPO
        readonly MODEL_FILE=Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf
        readonly MODEL_SHA=1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685
        ;;
    pq2_0)
        readonly MODEL_REVISION=5edf5f552d45e40b81f0255a8bb443af35850722
        readonly MODEL_REPO=https://huggingface.co/decent-jawfish/bonsai-2-27b-mtp/resolve/$MODEL_REVISION
        readonly MODEL_FILE=Bonsai-2-27B-PQ2_0-MTP.gguf
        readonly MODEL_SHA=78df4279d40ebebdccfd2dae0e9d4847afee52e94f48f3542ae9437220dbd847
        ;;
    *) echo 'Error: BONSAI_MODEL_VARIANT must be ptq1_0 or pq2_0.' >&2; return 2 ;;
esac
readonly VISION_REPO=https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/$VISION_REVISION
readonly VISION_FILE=Ternary-Bonsai-2-27B-mmproj-BF16.gguf
readonly VISION_SHA=e287342d92332fa3577ed1d42e921dac9370c08da58ba9337fa450f6cc76cfd7

# Standalone download tests also use this helper without the script logger.
_download_log() {
    if declare -F bonsai_log >/dev/null; then
        bonsai_log INFO "$*"
    else
        printf '[model-cache] [INFO] %s\n' "$*" >&2
    fi
}

# A directory lock works on shared filesystems without flock. Existing files
# are reused by default; verify/repair modes are explicit host operations.
_download_artifact() {
    set -euo pipefail
    local url=$1 destination=$2 expected_sha=$3 mode=${4:-reuse}
    local lock_dir="$destination.lock.d" curl_pid='' owned=false
    local wait_seconds=${BONSAI_DOWNLOAD_WAIT_SECONDS:-600}
    local download_timeout=${BONSAI_DOWNLOAD_TIMEOUT:-3600}
    local deadline missing_lock_retries=0 curl_status=0
    for value in "$wait_seconds" "$download_timeout"; do
        [[ "$value" =~ ^[0-9]{1,9}$ ]] && ((10#$value >= 1 && 10#$value <= 86400)) \
            || { echo 'Error: download wait/timeout must be integers from 1 to 86400 seconds.' >&2; exit 2; }
    done
    case "$mode" in reuse|verify|repair) ;; *) echo 'Error: invalid cache mode.' >&2; exit 2 ;; esac
    if [[ "$mode" == reuse && -s "$destination" && -r "$destination" ]]; then _download_log "Reusing readable cache file: $destination"; exit 0; fi
    mkdir -p -- "$(dirname -- "$destination")" || exit 2
    _download_log "Acquiring cache lock: $lock_dir (wait limit=${wait_seconds}s)."
    deadline=$((SECONDS + 10#$wait_seconds))
    while ! mkdir -- "$lock_dir" 2>/dev/null; do
        if [[ "$mode" == reuse && -s "$destination" && -r "$destination" ]]; then exit 0; fi
        # A lock can disappear between failed mkdir and this check. Retry that
        # race; repeated absence also bounds permanent permission/path errors.
        if [[ ! -d "$lock_dir" ]]; then
            missing_lock_retries=$((missing_lock_retries + 1))
            if ((missing_lock_retries >= 5)); then
                echo "Error: cannot create download lock in $(dirname -- "$destination"). Check write access." >&2
                exit 2
            fi
        else
            missing_lock_retries=0
        fi
        if ((SECONDS >= deadline)); then
            echo "Error: timed out waiting for $lock_dir. Stop all downloaders before removing a stale lock." >&2
            exit 2
        fi
        sleep 0.2
    done
    owned=true
    cleanup_download() {
        local status=$?
        if [[ -n "$curl_pid" ]]; then
            kill -TERM "$curl_pid" 2>/dev/null || true
            wait "$curl_pid" 2>/dev/null || true
        fi
        if [[ "$owned" == true ]]; then
            rm -f -- "$lock_dir/http-status"
            rmdir -- "$lock_dir" || true
        fi
        return "$status"
    }
    trap cleanup_download EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    checksum_matches() {
        [[ -r "$1" ]] && printf '%s  %s\n' "$expected_sha" "$1" | sha256sum --status -c -
    }
    if [[ -s "$destination" && -r "$destination" ]]; then
        if [[ "$mode" == reuse ]] || checksum_matches "$destination"; then _download_log "Cache ready: $destination (mode=$mode)."; exit 0; fi
        if [[ "$mode" == verify ]]; then
            echo "Error: cached file failed pinned checksum: $destination. Use --repair only for pinned artifacts." >&2
            exit 2
        fi
    elif [[ "$mode" == verify ]]; then
        echo "Error: cached file is missing: $destination" >&2
        exit 2
    fi
    # A complete verified partial file needs no Range request, including offline.
    if ! checksum_matches "$destination.part"; then
        _download_log "Downloading missing or damaged pinned model: $destination (timeout=${download_timeout}s)."
        curl --fail --location --retry 4 --connect-timeout 30 \
            --max-time "$download_timeout" --speed-limit 1024 --speed-time 60 \
            --continue-at - --write-out '%{http_code}' \
            --output "$destination.part" "$url" > "$lock_dir/http-status" &
        curl_pid=$!
        wait "$curl_pid" || curl_status=$?
        curl_pid=''
        # Servers that reject Range can be retried once from the beginning.
        if ((curl_status == 33)) || [[ $(cat "$lock_dir/http-status") == 416 ]]; then
            curl_status=0
            curl --fail --location --retry 4 --connect-timeout 30 \
                --max-time "$download_timeout" --speed-limit 1024 --speed-time 60 \
                --output "$destination.part" "$url" &
            curl_pid=$!
            wait "$curl_pid" || curl_status=$?
            curl_pid=''
        fi
        ((curl_status == 0)) || exit "$curl_status"
    fi
    _download_log "Verifying SHA256 before publishing: $destination"
    if ! checksum_matches "$destination.part"; then
        rm -f -- "$destination.part"
        echo "Error: model checksum failed: $destination" >&2
        exit 2
    fi
    # Repair preserves the previous destination until verified replacement.
    mv -- "$destination.part" "$destination" || exit 2
    _download_log "Verified artifact ready: $destination"
}

# The worker uses a function body rather than an extra subshell layer. The
# supervisor forwards signals even when this function itself runs in background.
download_missing_model() {
    local previous_traps download_worker status=0
    previous_traps=$(trap -p INT TERM)
    _download_artifact "$@" &
    download_worker=$!
    trap 'kill -TERM "$download_worker" 2>/dev/null || true; wait "$download_worker" 2>/dev/null || true; exit 143' TERM
    trap 'kill -TERM "$download_worker" 2>/dev/null || true; wait "$download_worker" 2>/dev/null || true; exit 130' INT
    wait "$download_worker" || status=$?
    trap - INT TERM
    eval "$previous_traps"
    return "$status"
}
