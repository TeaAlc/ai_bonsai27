#!/usr/bin/env -S python3 -B
"""Exercise immutable native helper/profile snapshots and failure policies."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


class NativeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/tmp/bonsai27')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'tools').mkdir(parents=True)
        (self.repo / 'data').mkdir()
        for path in (PROJECT / 'tools').glob('*'):
            if path.is_file():
                shutil.copy2(path, self.repo / 'tools' / path.name)
        shutil.copy2(PROJECT / 'data/logging.sh', self.repo / 'data/logging.sh')
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        source = self.root / 'source'
        source.mkdir()
        (source / 'LICENSE').write_text('fixture')
        archive = self.root / 'source.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(source, arcname='source')
        profiles = json.loads((self.repo / 'tools/backend-profiles.json').read_text())
        for profile in profiles.values():
            profile['source_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        (self.repo / 'tools/backend-profiles.json').write_text(json.dumps(profiles))
        binaries = self.root / 'bin'
        binaries.mkdir()
        (binaries / 'curl').write_text('#!/bin/bash\ncp "$FIXTURE_ARCHIVE" "${@: -1}"\n')
        (binaries / 'curl').chmod(0o755)
        (binaries / 'podman').write_text('''#!/usr/bin/env python3
import hashlib,json,os,pathlib,sys
args=sys.argv[1:]
mounts=[args[i+1] for i,arg in enumerate(args) if arg=='-v']
work=pathlib.Path(next(item.split(':/work:')[0] for item in mounts if ':/work:' in item))
tools=pathlib.Path(next(item.split(':/tools:')[0] for item in mounts if ':/tools:' in item))
profile=args[-1]
record=json.loads((tools/'backend-profiles.json').read_text())[profile]
assert (tools/'compile-backend.sh').is_file() and (tools/'package-backend.py').is_file()
original=(tools/'backend-profiles.json').read_bytes()
pathlib.Path('tools/backend-profiles.json').write_text('{}')
pathlib.Path('tools/compile-backend.sh').write_text('changed during compilation')
assert (tools/'backend-profiles.json').read_bytes()==original
if os.environ.get('FIXTURE_FAIL')=='1':sys.exit(33)
runtime=work/'runtime'
for name in ('bin/llama-server','lib/libggml-cuda.so.0','lib/libnccl.so.2'):
    path=runtime/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
for name in record['licenses']:
    path=runtime/'LICENSES'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
record['cmake_cache']=''.join(f'{key}:STRING={value}\\n' for key,value in record.pop('cmake_options').items())
(runtime/'build.json').write_text(json.dumps(record))
entries=[hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(runtime)) for path in sorted(runtime.rglob('*')) if path.is_file()]
(runtime/'SHA256SUMS').write_text('\\n'.join(entries)+'\\n')
''')
        (binaries / 'podman').chmod(0o755)
        self.env = dict(os.environ, PATH=str(binaries) + ':' + os.environ['PATH'],
                        TMPDIR=str(self.root / 'tmp'), FIXTURE_ARCHIVE=str(archive),
                        PYTHONDONTWRITEBYTECODE='1')

    def run_build(self, profile, fail=False):
        return subprocess.run(['bash', str(self.repo / f'tools/build-{profile}-backend.sh')],
                              cwd=self.repo, env=dict(self.env, FIXTURE_FAIL='1' if fail else '0'),
                              capture_output=True, text=True, timeout=30)

    def test_snapshot_survives_checkout_mutation(self):
        result = self.run_build('ada')
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.repo / 'data/backends/ada-source/runtime/build.json').read_text())
        self.assertEqual(record['architectures'], ['89-real'])
        self.assertEqual(json.loads((self.repo / 'tools/backend-profiles.json').read_text()), {})

    def test_blackwell_snapshot(self):
        result = self.run_build('blackwell')
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.repo / 'data/backends/blackwell-source/runtime/build.json').read_text())
        self.assertEqual(record['architectures'], ['120-real'])

    def test_ada_failure_cleans_objects(self):
        result = self.run_build('ada', True)
        self.assertEqual(result.returncode, 33, result.stderr)
        self.assertFalse(list((self.root / 'tmp').glob('ada-source.*')))

    def test_blackwell_failure_retains_objects(self):
        result = self.run_build('blackwell', True)
        self.assertEqual(result.returncode, 33, result.stderr)
        self.assertEqual(len(list((self.root / 'tmp').glob('blackwell-source.*'))), 1)


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
