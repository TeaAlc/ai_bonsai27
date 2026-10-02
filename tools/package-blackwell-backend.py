#!/usr/bin/env -S python3 -B
"""Package the pinned compiler output, runtime libraries, and licenses."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

work = Path(sys.argv[1])
root = work / 'runtime'
for directory in ('bin', 'lib', 'LICENSES'):
    (root / directory).mkdir(parents=True, exist_ok=True)
for name in ('llama-server', 'test-backend-ops'):
    shutil.copy2(work / 'build/bin' / name, root / 'bin' / name)
# Dereference SONAME links: the inventory verifier rejects symlinks.
for path in (work / 'build/bin').glob('*.so*'):
    if path.name.endswith('.so.0') or (not path.is_symlink() and path.name.endswith('.so')):
        shutil.copy2(path.resolve(), root / 'lib' / path.name)
for name in ('libcudart.so.12', 'libcublas.so.12', 'libcublasLt.so.12'):
    shutil.copy2((Path('/usr/local/cuda/lib64') / name).resolve(), root / 'lib' / name)
for name in ('libgomp.so.1', 'libnccl.so.2'):
    shutil.copy2((Path('/usr/lib/x86_64-linux-gnu') / name).resolve(), root / 'lib' / name)
licenses = {
    'libgomp-copyright.txt': '/usr/share/doc/libgomp1/copyright',
    'llama.cpp-LICENSE.txt': work / 'source/LICENSE',
    'cuda-cudart-copyright.txt': '/usr/share/doc/cuda-cudart-12-8/copyright',
    'cublas-copyright.txt': '/usr/share/doc/libcublas-12-8/copyright',
    'NCCL-copyright.txt': '/usr/share/doc/libnccl2/copyright',
}
for name, source in licenses.items():
    shutil.copy2(source, root / 'LICENSES' / name)
record = {
    'source_revision': 'f13265492743209a0fbedc2a2781af3f5f0eab13',
    'source_sha256': '0368b7a5aa02215cafd72b590162ae6b87ca1690be18445c9af7a53145d4c2d5',
    'compiler_image': 'docker.io/nvidia/cuda@sha256:4b9ed5fa8361736996499f64ecebf25d4ec37ff56e4d11323ccde10aa36e0c43',
    'architectures': ['120-real'],
    'cmake_cache': (work / 'build/CMakeCache.txt').read_text(),
    'packages': subprocess.check_output(['dpkg-query', '-W'], text=True),
}
(root / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
entries = []
for path in sorted(root.rglob('*')):
    if path.is_file() and path.name != 'SHA256SUMS':
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        entries.append(digest + '  ' + str(path.relative_to(root)))
(root / 'SHA256SUMS').write_text('\n'.join(entries) + '\n')
print('Packaged', root)
