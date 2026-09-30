#!/usr/bin/env bash
set -euo pipefail

# Send the project image to an OpenAI-compatible vision endpoint.
# An explicit hostname[:port] overrides BONSAI_BASE_URL. Without either, use localhost:8080.
if (( $# > 1 )); then
    echo 'Usage: ./simple_request.sh [hostname[:port]]' >&2
    exit 2
fi

if (( $# == 1 )); then
    # Accept a hostname or IPv4 address, optionally followed by a TCP port.
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

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BONSAI_IMAGE_PATH="$script_dir/assets/fairyland-unicorns-1080p.png"
export BONSAI_BASE_URL="${BONSAI_BASE_URL:-http://localhost:8080}"

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
