#!/usr/bin/env -S python3 -B
"""The optional runtime must reject changed files, pins, and architectures."""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('blackwell_source', Path(__file__).resolve().parents[1] / 'tools/verify-blackwell-source.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/tmp/bonsai27')
        self.root = Path(self.temp.name)
        for name in ('bin/llama-server', 'lib/libggml-cuda.so.0', 'lib/libnccl.so.2',
                     'LICENSES/llama.cpp-LICENSE.txt', 'LICENSES/NCCL-copyright.txt'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        self.record = {'source_revision': module.SOURCE_REVISION, 'source_sha256': module.SOURCE_SHA256,
                       'compiler_image': module.COMPILER_IMAGE, 'architectures': ['120-real'], 'cmake_cache': 'CMAKE_CUDA_ARCHITECTURES:STRING=120-real\nGGML_CUDA:BOOL=ON\nGGML_CUDA_FA:BOOL=ON\nGGML_CUDA_GRAPHS:BOOL=ON\n'}
        self.write_inventory()

    def tearDown(self):
        self.temp.cleanup()

    def write_inventory(self):
        (self.root / 'build.json').write_text(json.dumps(self.record))
        entries = []
        for path in sorted(self.root.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                entries.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + str(path.relative_to(self.root)))
        (self.root / 'SHA256SUMS').write_text('\n'.join(entries) + '\n')

    def test_valid(self):
        self.assertEqual(len(module.verify(self.root)), 64)

    def test_changed_file(self):
        (self.root / 'bin/llama-server').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            module.verify(self.root)

    def test_unlisted_file(self):
        (self.root / 'lib/unlisted.so').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'inventory mismatch'):
            module.verify(self.root)

    def test_compiler_cache_with_comments_and_blank_lines(self):
        self.record['cmake_cache'] = '# Generated CMake cache\n// option descriptions\n\n' + self.record['cmake_cache']
        self.write_inventory()
        self.assertEqual(len(module.verify(self.root)), 64)

    def test_wrong_actual_compiler_architecture(self):
        self.record['cmake_cache'] = self.record['cmake_cache'].replace('120-real', '89-real')
        self.write_inventory()
        with self.assertRaisesRegex(ValueError, 'Blackwell compiler option'):
            module.verify(self.root)

    def test_wrong_pin_and_architecture(self):
        for key, value in [('source_revision', 'unreviewed'), ('source_sha256', 'unverified'),
                           ('compiler_image', 'latest'), ('architectures', ['86-real'])]:
            original = self.record[key]
            self.record[key] = value
            self.write_inventory()
            with self.assertRaisesRegex(ValueError, 'unpinned Blackwell source'):
                module.verify(self.root)
            self.record[key] = original


if __name__ == '__main__':
    unittest.main()
