#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# A populated pinned cache must serve the OpenAI API without outbound networking.
model_dir=${BONSAI_MODEL_DIR:-"$PWD"}
model_dir=$(cd -- "$model_dir" && pwd)
container="bonsai-offline-test-$$"
cleanup() { podman rm --force "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
if [[ -e /dev/dxg ]]; then
    gpu_args=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro)
else
    gpu_args=(--device nvidia.com/gpu=all)
fi
podman run -d --name "$container" --network none "${gpu_args[@]}" \
    --security-opt label=disable -v "$model_dir:/models:rw" -e BONSAI_CTX_SIZE=8192 \
    "${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}" >/dev/null
ready=false
for ((attempt=0;attempt<150;attempt++)); do
    if podman exec "$container" curl --fail --silent --max-time 2 http://localhost:8080/health >/dev/null; then
        ready=true
        break
    fi
    sleep .2
done
[[ "$ready" == true ]] || { podman logs "$container"; exit 1; }
podman exec "$container" curl --fail --silent --max-time 60 \
    -H 'Content-Type: application/json' \
    --data '{"model":"bonsai2-27b","messages":[{"role":"user","content":"Reply with only the number: What is 19 + 23?"}],"temperature":0,"max_tokens":64,"chat_template_kwargs":{"enable_thinking":false}}' \
    http://localhost:8080/v1/chat/completions | \
    python3 -B -c 'import json,sys; assert json.load(sys.stdin)["choices"][0]["message"]["content"].strip() == "42"'
logs=$(podman logs "$container" 2>&1)
[[ "$logs" != *'Downloading missing'* ]]
echo 'Passed warm-cache offline startup and an actual OpenAI API request with networking disabled.'
