#!/usr/bin/env bash
set -euo pipefail

# Send the project image to the local OpenAI-compatible vision endpoint.
# Override BONSAI_BASE_URL when the container was started with a different BONSAI_PORT.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BONSAI_IMAGE_PATH="$script_dir/assets/fairyland-unicorns-1080p.png"
export BONSAI_BASE_URL="${BONSAI_BASE_URL:-http://127.0.0.1:8080}"

if [[ ! -r "$BONSAI_IMAGE_PATH" ]]; then
    echo "Image is missing: $BONSAI_IMAGE_PATH" >&2
    exit 2
fi

# Disable Python bytecode caches for this request and its imports.
python3 -B - <<'PY'
import base64
import json
import os
import urllib.request
from pathlib import Path

image = base64.b64encode(Path(os.environ['BONSAI_IMAGE_PATH']).read_bytes()).decode('ascii')
payload = {
    'model': 'bonsai2-27b',
    'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'What is visible in this image?'},
        {'type': 'image_url', 'image_url': {
            'url': 'data:image/png;base64,' + image
        }},
    ]}],
    'temperature': 0,
    'max_tokens': 512,
    'chat_template_kwargs': {'enable_thinking': False},
}
request = urllib.request.Request(
    os.environ['BONSAI_BASE_URL'].rstrip('/') + '/v1/chat/completions',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(request, timeout=300) as response:
    result = json.load(response)
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
