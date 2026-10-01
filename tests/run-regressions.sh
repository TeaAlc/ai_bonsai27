#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# Fixtures never publish images or modify this checkout's Git refs.
for test in test-logging test-version test-create-release test-release-tag test-model-download test-gpu-backend test-cuda-probe test-settings test-simple-request test-run-image; do
    bash "tests/$test.sh"
done
for test in test-image-push test-registry test-published-release test-download-signals test-backend-prepare test-build-snapshot test-qa-evidence test-api-support test-text-benchmark; do
    python3 -B "tests/$test.py"
done
