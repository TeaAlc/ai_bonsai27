#!/usr/bin/env -S python3 -B
"""Check the optional SM120 runtime inventory and pinned build provenance."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
import re
from pathlib import Path

from backend_profile import load


def verify(root, name):
    profile = load(name)
    label = "Ada" if name == "ada" else "Blackwell"
    root = Path(root)
    module_path = Path(__file__).with_name('verify-backend.py')
    spec = importlib.util.spec_from_file_location('backend_inventory', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.verify(root)
    record = json.loads((root / 'build.json').read_text())
    expected = {key: profile[key] for key in ('source_revision', 'source_sha256', 'compiler_image', 'architectures')}
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f'unpinned {label} source build: {key}')
    # Check actual compiler cache entries as well as the declared architecture.
    # This rejects a mistakenly packaged Ada build before it reaches an image.
    cache = dict(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*):[^=\r\n]+=([^\r\n]*)$', record.get('cmake_cache', ''), re.MULTILINE))
    options = profile['cmake_options']
    for key, value in options.items():
        if cache.get(key) != value:
            raise ValueError(f'unpinned {label} compiler option: {key}')
    required = ('bin/llama-server', 'lib/libggml-cuda.so.0', 'lib/libnccl.so.2',
                'LICENSES/llama.cpp-LICENSE.txt', 'LICENSES/NCCL-copyright.txt')
    for name in required:
        if not (root / name).is_file():
            raise ValueError(f'missing {label} source runtime file: {name}')
    for license_name in profile["licenses"]:
        if not (root / "LICENSES" / license_name).is_file():
            raise ValueError(f"Missing required license: {license_name}")
    return manifest


if __name__ == '__main__':
    try:
        print(verify(sys.argv[1], sys.argv[2]))
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(2)
