#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# Fixtures never publish images or modify this checkout's Git refs.
for test in test-logging test-version test-create-release test-release-tag test-model-download test-gpu-backend test-cuda-probe test-settings test-simple-request test-run-image; do
    bash "tests/$test.sh"
done
for test in test-image-push test-registry test-published-release test-download-signals test-backend-prepare test-ada-source test-blackwell-source test-build-snapshot test-qa-evidence test-api-support test-text-benchmark test-gpu-memory-summary test-nvidia-setup test-config test-benchmark-evidence test-native-build test-compare-benchmarks test-package-backend test-benchmark-worker; do
    python3 -B "tests/$test.py"
done
