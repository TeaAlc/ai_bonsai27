#!/usr/bin/env -S python3 -B
"""Exercise the common packager for both profiles without host CUDA installs."""
import sys
sys.dont_write_bytecode = True
import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from backend_profile import load


class PackageTests(unittest.TestCase):
    def test_both_profiles_keep_pins_flags_libraries_and_licenses(self):
        for name in ('ada', 'blackwell'):
            with self.subTest(profile=name), tempfile.TemporaryDirectory(dir='/tmp/bonsai27') as temporary:
                work = Path(temporary)
                (work / 'build/bin').mkdir(parents=True)
                (work / 'source').mkdir()
                for binary in ('llama-server', 'test-backend-ops'):
                    (work / 'build/bin' / binary).write_text('fixture executable')
                (work / 'build/bin/libggml-cuda.so.0').write_text('fixture CUDA backend')
                (work / 'source/LICENSE').write_text('fixture upstream license')
                profile = load(name)
                (work / 'build/CMakeCache.txt').write_text(''.join(f'{key}:STRING={value}\n' for key, value in profile['cmake_options'].items()))
                original_copy = shutil.copy2

                def copy(source, target):
                    # Represent compiler-image system libraries/licenses locally.
                    # No files under /usr are created or altered by this fixture.
                    if str(source).startswith('/usr/'):
                        Path(target).write_text('fixture system dependency')
                    else:
                        original_copy(source, target)

                with patch.object(sys, 'argv', ['package-backend.py', str(work), name]), \
                     patch('shutil.copy2', side_effect=copy), \
                     patch('subprocess.check_output', return_value='fixture-package\t1.0\n'):
                    runpy.run_path(str(TOOLS / 'package-backend.py'), run_name='__main__')
                verifier = runpy.run_path(str(TOOLS / 'verify-source.py'))['verify']
                self.assertEqual(len(verifier(work / 'runtime', name)), 64)
                record = json.loads((work / 'runtime/build.json').read_text())
                self.assertEqual(record['architectures'], profile['architectures'])
                self.assertEqual(record['source_sha256'], profile['source_sha256'])
                self.assertIn('backend-profiles.json', record['compiler_helpers'])
                self.assertFalse(list((work / 'runtime').rglob('libcuda.so*')))
                for license_name in profile['licenses']:
                    self.assertTrue((work / 'runtime/LICENSES' / license_name).is_file())


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
