#!/usr/bin/env bash
# Source from the benchmark harness; manage only its owned timeout group.
worker_pid=
# GNU timeout owns a process group. Run it asynchronously so Bash's wait
# builtin can react immediately to INT/TERM instead of deferring the trap.
# Preserve stdin explicitly for the readiness helper's Python here-document.
run_worker() {
    "$@" <&0 &
    worker_pid=$!
    local status=0
    wait "$worker_pid" || status=$?
    worker_pid=
    return "$status"
}
stop_worker() {
    if [[ -n "$worker_pid" ]]; then
        # Signal only this run's timeout group, including its Python client.
        kill -TERM -- "-$worker_pid" 2>/dev/null || kill -TERM "$worker_pid" 2>/dev/null || true
        wait "$worker_pid" 2>/dev/null || true
        worker_pid=
    fi
}
