#!/usr/bin/env bash
# Write progress to stderr so command substitutions retain clean return values.
# Never print command text: it can contain registry tokens or other credentials.
bonsai_stage=initialization
bonsai_log() {
    local level=$1
    shift
    printf '[%s] [%s] [%s] [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "${bonsai_component:-bonsai}" "$bonsai_stage" "$level" "$*" >&2
}
bonsai_step() {
    bonsai_stage=$1
    shift
    bonsai_log INFO "$*"
}
bonsai_error() {
    local status=$1 line=$2
    bonsai_log ERROR "Step failed (exit=$status, line=$line). See the preceding diagnostic."
}
bonsai_init_logging() {
    bonsai_component=$1
    set -E
    trap 'bonsai_error "$?" "$LINENO"' ERR
}
