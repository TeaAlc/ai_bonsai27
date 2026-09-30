"""Shared API transport and evidence tied to one running container."""
import sys
sys.dont_write_bytecode = True
import datetime
import json
import os
import subprocess
import shutil
import time
import uuid
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get('BONSAI_BASE_URL', 'http://127.0.0.1:8080').rstrip('/')
CONTAINER = os.environ.get('BONSAI_TEST_CONTAINER', 'bonsai2-27b')
# A run directory is mandatory: silently mixing old fixed-path results is unsafe.
if not os.environ.get('BONSAI_TEST_RUN_DIR') or not os.environ.get('BONSAI_TEST_SUITE_ID'):
    raise RuntimeError('Use tests/run-qa.sh, or set BONSAI_TEST_RUN_DIR and BONSAI_TEST_SUITE_ID explicitly.')
RUN_DIR = Path(os.environ['BONSAI_TEST_RUN_DIR'])
RUN_DIR.mkdir(parents=True, exist_ok=True)


def call(path, data=None, timeout=600):
    request = urllib.request.Request(BASE_URL + path,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def wait_ready(seconds=None):
    seconds = seconds if seconds is not None else int(os.environ.get('BONSAI_TEST_READY_SECONDS', '600'))
    if not 1 <= seconds <= 3600: raise ValueError('BONSAI_TEST_READY_SECONDS must be 1–3600')
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if call('/health', timeout=min(3, max(.1, deadline-time.monotonic()))).get('status') == 'ok': return
        except Exception:
            pass
        time.sleep(.5)
    raise RuntimeError(f'Server did not become ready within {seconds}s')


def save(name, data):
    path = RUN_DIR / (name + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {'run_id': identity()['run_id'], 'image_id': identity()['image_id'],
                'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'data': data}
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + '\n')


def identity():
    # Inspect again when saving so a replaced container cannot inherit evidence.
    info = json.loads(subprocess.check_output(['podman', 'inspect', CONTAINER], text=True))[0]
    image_id = 'sha256:' + info['Image'].removeprefix('sha256:')
    path = RUN_DIR / 'identity.json'
    if path.exists():
        record = json.loads(path.read_text())
        if record['image_id'] != image_id or record['container_id'] != info['Id']:
            raise ValueError('container changed during this test run')
        return record
    labels = info['Config']['Labels']
    environment = dict(value.split('=', 1) for value in info['Config'].get('Env', []))
    model = environment.get('BONSAI_MODEL', '/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf')
    vision = environment.get('BONSAI_MMPROJ', '/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf')
    hashes = subprocess.check_output(['podman', 'exec', CONTAINER, 'sha256sum', model, vision], text=True)
    capability = subprocess.check_output(['podman', 'exec', CONTAINER, 'bash', '-c', 'source /opt/bonsai/detect-gpu.sh; query_cuda_capability'], text=True).strip()
    smi = '/usr/lib/wsl/lib/nvidia-smi' if Path('/usr/lib/wsl/lib/nvidia-smi').exists() else shutil.which('nvidia-smi')
    inventory = None
    if smi:
        result = subprocess.run([smi, '--query-gpu=name,driver_version,uuid', '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0: inventory = result.stdout.strip().splitlines()
    record = {'run_id': uuid.uuid4().hex, 'suite_id': os.environ['BONSAI_TEST_SUITE_ID'], 'image_id': image_id, 'container_id': info['Id'],
              'revision': labels['org.opencontainers.image.revision'],
              'version': labels['org.opencontainers.image.version'],
              'dirty': labels['io.bonsai.git.dirty'], 'base_url': BASE_URL,
              'context': int(os.environ.get('BONSAI_CTX_SIZE', '16384')),
              'compute_capability': capability,
              'backend': 'blackwell' if capability == '12.0' else 'ampere-ada',
              'model_hashes': hashes.splitlines(), 'host_gpu_inventory': inventory,
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    path.write_text(json.dumps(record, indent=2) + '\n')
    return record
