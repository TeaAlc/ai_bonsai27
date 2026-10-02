#!/usr/bin/env -S python3 -B
"""Check the optional SM120 runtime inventory and pinned build provenance."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
import re
from pathlib import Path

SOURCE_REVISION = 'f13265492743209a0fbedc2a2781af3f5f0eab13'
SOURCE_SHA256 = '0368b7a5aa02215cafd72b590162ae6b87ca1690be18445c9af7a53145d4c2d5'
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
                'compiler_image': COMPILER_IMAGE, 'architectures': ['120-real']}
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f'unpinned Blackwell source build: {key}')
    # Check actual compiler cache entries as well as the declared architecture.
    # This rejects a mistakenly packaged Ada build before it reaches an image.
    cache = dict(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*):[^=\r\n]+=([^\r\n]*)$', record.get('cmake_cache', ''), re.MULTILINE))
    options = {'CMAKE_CUDA_ARCHITECTURES': '120-real', 'GGML_CUDA': 'ON',
               'GGML_CUDA_FA': 'ON', 'GGML_CUDA_GRAPHS': 'ON'}
    for key, value in options.items():
        if cache.get(key) != value:
            raise ValueError(f'unpinned Blackwell compiler option: {key}')
    required = ('bin/llama-server', 'lib/libggml-cuda.so.0', 'lib/libnccl.so.2',
                'LICENSES/llama.cpp-LICENSE.txt', 'LICENSES/NCCL-copyright.txt')
    for name in required:
        if not (root / name).is_file():
            raise ValueError(f'missing Blackwell source runtime file: {name}')
    return manifest


if __name__ == '__main__':
    try:
        print(verify(sys.argv[1]))
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(2)
