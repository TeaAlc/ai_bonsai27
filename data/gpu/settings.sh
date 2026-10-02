#!/usr/bin/env bash
# Reject oversized decimal strings before Bash arithmetic can wrap.
validate_decimal() {
    local name=$1 value=$2 minimum=$3 maximum=$4
    if [[ ! "$value" =~ ^[0-9]+$ || ${#value} -gt 9 ]]; then
        echo "Error: $name must be an integer from $minimum to $maximum." >&2
        return 2
    fi
    if (( 10#$value < minimum || 10#$value > maximum )); then
        echo "Error: $name must be an integer from $minimum to $maximum." >&2
        return 2
    fi
}

validate_bonsai_settings() {
    validate_decimal BONSAI_CTX_SIZE "${BONSAI_CTX_SIZE:-32000}" 512 262144 || return
    validate_decimal BONSAI_DOWNLOAD_WAIT_SECONDS "${BONSAI_DOWNLOAD_WAIT_SECONDS:-600}" 1 86400 || return
    validate_decimal BONSAI_DOWNLOAD_TIMEOUT "${BONSAI_DOWNLOAD_TIMEOUT:-3600}" 1 86400 || return
    case "${BONSAI_REASONING_EFFORT:-medium}" in
        low|medium|xhigh) ;;
        *) echo 'Error: BONSAI_REASONING_EFFORT must be low, medium, or xhigh.' >&2; return 2 ;;
    esac
    case "${BONSAI_GPU_BACKEND:-}" in
        ''|blackwell|ampere-ada) ;;
        *) echo 'Error: BONSAI_GPU_BACKEND must be blackwell or ampere-ada, or empty for detection.' >&2; return 2 ;;
    esac
}
