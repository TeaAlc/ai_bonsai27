#!/usr/bin/env -S python3 -B
"""Check the optional SM89 runtime inventory and pinned build provenance."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
from pathlib import Path

SOURCE_REVISION = '88c4bc60b9c9578f134385be9535e853f2db9b9f'
SOURCE_SHA256 = 'cd55b6c23f1ef81c8bd9980ae148b66aeac1bc56b4eaed468b40d2a1247aed7b'
COMPILER_IMAGE = 'docker.io/nvidia/cuda@sha256:4b9ed5fa8361736996499f64ecebf25d4ec37ff56e4d11323ccde10aa36e0c43'


def verify(root):
    root = Path(root)
    module_path = Path(__file__).with_name('verify-backend.py')
    spec = importlib.util.spec_from_file_location('backend_inventory', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.verify(root)
    record = json.loads((root / 'build.json').read_text())
    expected = {'source_revision': SOURCE_REVISION, 'source_sha256': SOURCE_SHA256,
                'compiler_image': COMPILER_IMAGE, 'architectures': ['89-real']}
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f'unpinned Ada source build: {key}')
    required = ('bin/llama-server', 'lib/libggml-cuda.so.0', 'lib/libnccl.so.2',
                'LICENSES/llama.cpp-LICENSE.txt', 'LICENSES/NCCL-copyright.txt')
    for name in required:
        if not (root / name).is_file():
            raise ValueError(f'missing Ada source runtime file: {name}')
    return manifest


if __name__ == '__main__':
    try:
        print(verify(sys.argv[1]))
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(2)
