#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# Each run owns its containers and output tree. The nondefault port verifies
# that all API tests honor the same endpoint rather than silently using 8080.
run_id=$(date -u +%Y%m%dT%H%M%SZ)-$$
export BONSAI_TEST_SUITE_ID="$run_id"
export BONSAI_TEST_RUN_DIR="$PWD/results/runs/$run_id"
export BONSAI_TEST_CONTAINER="bonsai-qa-$run_id"
export BONSAI_CONTAINER_NAME="$BONSAI_TEST_CONTAINER"
export BONSAI_PORT=${BONSAI_PORT:-18080}
export BONSAI_BASE_URL="http://127.0.0.1:$BONSAI_PORT"
export BONSAI_CTX_SIZE=16384
export BONSAI_MODEL_DIR=${BONSAI_MODEL_DIR:-"$PWD"}
mkdir -p "$BONSAI_TEST_RUN_DIR"
cleanup() {
    if podman container exists "$BONSAI_TEST_CONTAINER"; then
        mkdir -p "$BONSAI_TEST_RUN_DIR"
        podman logs "$BONSAI_TEST_CONTAINER" > "$BONSAI_TEST_RUN_DIR/last-container.log" 2>&1 || true
        podman rm --force "$BONSAI_TEST_CONTAINER" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
./run.sh --log-verbose
python3 -B tests/test-api.py
python3 -B tests/test-vision.py
python3 -B tests/test-coding.py
./simple_request.sh "127.0.0.1:$BONSAI_PORT" > "$BONSAI_TEST_RUN_DIR/unicorn-response.json"
podman logs "$BONSAI_TEST_CONTAINER" > "$BONSAI_TEST_RUN_DIR/server.log" 2>&1
PYTHONPATH="$PWD/tests" python3 -B - <<'PY'
import hashlib
from api_support import RUN_DIR, save
save('server-log', {'sha256': hashlib.sha256((RUN_DIR / 'server.log').read_bytes()).hexdigest()})
PY
cleanup
suite_dir=$BONSAI_TEST_RUN_DIR
export BONSAI_TEST_RUN_DIR="$suite_dir/context-8192"
export BONSAI_CTX_SIZE=8192
./run.sh --log-verbose
PYTHONPATH="$PWD/tests" python3 -B - <<'PY'
from api_support import call, save, wait_ready, identity
wait_ready()
identity()
props = call('/props')
assert props['default_generation_settings']['n_ctx'] == 8192
save('props', props)
PY
podman logs "$BONSAI_TEST_CONTAINER" > "$BONSAI_TEST_RUN_DIR/server.log" 2>&1
python3 -B tests/qa.py "$suite_dir"
echo "QA evidence: $suite_dir"
