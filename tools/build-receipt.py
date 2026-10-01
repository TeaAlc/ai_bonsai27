#!/usr/bin/env -S python3 -B
"""Record an inspected build and its actual dependency inventory atomically."""
import sys
sys.dont_write_bytecode = True
import datetime
import hashlib
import json
import os
from pathlib import Path

staging, version, revision, dirty, destination = sys.argv[1:]
root = Path(staging)
image = json.loads((root / 'image.json').read_text())[0]
labels = image['Config']['Labels']
expected = {'org.opencontainers.image.version': version,
            'org.opencontainers.image.revision': revision,
            'io.bonsai.git.dirty': dirty,
            'org.opencontainers.image.source': 'https://github.com/TeaAlc/ai_bonsai27'}
if any(labels.get(key) != value for key, value in expected.items()):
    raise ValueError('built image labels do not match intended source')
inputs = {}
for backend in ('blackwell', 'ampere-ada'):
    manifest = root / 'data/backends' / backend / 'runtime/SHA256SUMS'
    inputs[backend] = hashlib.sha256(manifest.read_bytes()).hexdigest()
optional_backend = root / 'data/backends/ada-source/runtime'
optional_build = None
if (optional_backend / 'SHA256SUMS').is_file():
    inputs['ada-source'] = hashlib.sha256((optional_backend / 'SHA256SUMS').read_bytes()).hexdigest()
    optional_build = json.loads((optional_backend / 'build.json').read_text())
record = {'schema': 1, 'image_id': 'sha256:' + image['Id'].removeprefix('sha256:'), 'engine': 'podman',
          'version': version, 'revision': revision, 'dirty': dirty == 'true',
          'source': expected['org.opencontainers.image.source'],
          'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'inputs': inputs, 'ada_source_build': optional_build, 'containerfile': (root / 'Containerfile').read_text(),
          'backend_pins': (root / 'tools/backend-artifacts.sh').read_text(),
          'model_pins': (root / 'data/models/download.sh').read_text().split('# A directory lock')[0],
          'semrel_pins': (root / 'tools/semrel/artifacts.sh').read_text(),
          'packages': (root / 'packages.txt').read_text().splitlines(),
          'repo_digests': image.get('RepoDigests', [])}
path = Path(destination)
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(record, indent=2) + '\n')
os.replace(temporary, path)
