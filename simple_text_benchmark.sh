#!/usr/bin/env bash
set -euo pipefail

# Simulate 10 user/assistant exchanges (20 messages), retaining full history.
# Benchmarks always enable thinking at medium effort. The ~16k cumulative
# usage target can be exceeded by complete reasoning; never truncate to fit it.
if (( $# > 1 )); then
    echo 'Usage: ./simple_text_benchmark.sh [hostname[:port]]' >&2
    exit 2
fi
if (( $# == 1 )); then
    if [[ ! "$1" =~ ^([[:alnum:]_.-]+)(:([0-9]+))?$ ]]; then
        echo 'Error: expected hostname or hostname:port.' >&2
        exit 2
    fi
    hostname=${BASH_REMATCH[1]}
    port=${BASH_REMATCH[3]:-8080}
    if (( ${#port} > 5 )) || (( 10#$port < 1 || 10#$port > 65535 )); then
        echo 'Error: port must be between 1 and 65535.' >&2
        exit 2
    fi
    BONSAI_BASE_URL="http://$hostname:$port"
fi
export BONSAI_BASE_URL="${BONSAI_BASE_URL:-http://localhost:8080}"
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BONSAI_BENCHMARK_RESULT="${BONSAI_BENCHMARK_RESULT:-$project_dir/results/text-benchmark/$(date -u +%Y%m%dT%H%M%SZ)-$$.json}"

# Use only the Python standard library; never create bytecode caches.
exec python3 -B "$project_dir/tests/text_benchmark.py"
