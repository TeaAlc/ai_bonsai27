#!/usr/bin/env -S python3 -B
"""Capture and audit portable, checksum-bound container benchmark evidence."""
import sys
sys.dont_write_bytecode = True
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

SCHEMA = 1


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
    os.replace(stream.name, path)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def engine(*args):
    return subprocess.check_output(['podman', *args])


def capture(root, name, base, suite, repetition):
    root = Path(root)
    container = json.loads(engine('inspect', name))[0]
    image = json.loads(engine('image', 'inspect', container['Image']))[0]
    with urllib.request.urlopen(base + '/props', timeout=10) as response:
        props = json.load(response)
    identity = {
        'schema_version': SCHEMA, 'suite_id': suite, 'run_id': root.name,
        'repetition': int(repetition), 'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'image_id': 'sha256:' + container['Image'].removeprefix('sha256:'), 'container_id': container['Id'],
        'image_labels': image.get('Labels') or image.get('Config', {}).get('Labels'),
        'container': container, 'props': props,
        'executable': engine('exec', name, 'readlink', '/proc/1/exe').decode().strip(),
        'argv': engine('exec', name, 'cat', '/proc/1/cmdline').decode().strip('\0').split('\0'),
        'evidence_scope': 'identified-container',
    }
    # Hash model files in the container: this also works with custom mounts.
    # No CUDA libraries or credentials are copied into evidence.
    args = identity['argv']
    models = {}
    for flag in ('--model', '--mmproj', '--spec-draft-model'):
        if flag in args:
            filename = args[args.index(flag) + 1]
            models[flag] = {'path': filename, 'sha256': engine('exec', name, 'sha256sum', filename).decode().split()[0]}
    identity['models'] = models
    identity['compute_capability'] = engine('exec', name, 'bash', '-c', 'source /opt/bonsai/detect-gpu.sh; query_cuda_capability').decode().strip()
    smi = '/usr/lib/wsl/lib/nvidia-smi' if Path('/usr/lib/wsl/lib/nvidia-smi').exists() else shutil.which('nvidia-smi')
    identity['host_gpu_inventory'] = None
    if smi:
        result = subprocess.run([smi, '-i', '0', '--query-gpu=name,uuid,driver_version,memory.total,memory.used,temperature.gpu,utilization.gpu', '--format=csv'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            identity['host_gpu_inventory'] = result.stdout
    atomic_json(root / 'identity.json', identity)
    finalize(root, 'running', 0)


def diagnostic_json(path):
    """Cleanup must survive a worker interrupted while writing diagnostic JSON."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def finalize(root, status, exit_status, stage=None):
    root = Path(root)
    files = {str(path.relative_to(root)): digest(path) for path in sorted(root.rglob('*'))
             if path.is_file() and path.name != 'benchmark-index.json'}
    identity_path = root / 'identity.json'
    identity = diagnostic_json(identity_path)
    index = {'schema_version': SCHEMA, 'suite_id': identity.get('suite_id'),
             'run_id': root.name, 'repetition': identity.get('repetition'),
             'image_id': identity.get('image_id'), 'container_id': identity.get('container_id'),
             'status': status, 'exit_status': int(exit_status), 'files': files}
    report_path = root / 'benchmark.json'
    report = diagnostic_json(report_path)
    quality_path = root / 'quality/quality/summary.json'
    quality = diagnostic_json(quality_path).get('data', [])
    if not isinstance(quality, list) or not all(isinstance(row, dict) and 'passed' in row for row in quality):
        quality = []
    index['benchmark_status'] = report.get('status', 'completed' if report.get('completed_exchanges') == 10 else 'unknown')
    index['quality_status'] = ('passed' if len(quality) == 9 and all(row['passed'] for row in quality) else 'failed') if quality else 'unknown'
    index['failure_stage'] = stage if status not in ('completed', 'running') else None
    index['primary_error'] = report.get('error')
    atomic_json(root / 'benchmark-index.json', index)


def suite_index(root):
    root = Path(root)
    runs = []
    seen = set()
    for path in sorted(root.glob('run-*/benchmark-index.json')):
        item = json.loads(path.read_text())
        identity = (item['suite_id'], item['repetition'])
        if identity in seen:
            raise ValueError('Duplicate repetition identity')
        seen.add(identity)
        runs.append({'path': str(path.relative_to(root)), 'sha256': digest(path),
                     'run_id': item['run_id'], 'status': item['status'],
                     'repetition': item['repetition'], 'image_id': item['image_id']})
    metadata = root / 'suite.json'
    expected = json.loads(metadata.read_text())['repetitions'] if metadata.exists() else len(runs)
    atomic_json(root / 'benchmark-index.json', {'schema_version': SCHEMA,
        'suite_id': root.name, 'runs': runs, 'expected_repetitions': expected,
        'status': 'completed' if runs and len(runs) == expected and all(row['status'] == 'completed' for row in runs) else 'partial'})


def close_number(actual, expected):
    if actual is None or expected is None:
        return actual is expected
    return abs(actual - expected) <= 0.015


def audit(root):
    root = Path(root).resolve()
    index = json.loads((root / 'benchmark-index.json').read_text())
    if index['schema_version'] != SCHEMA or index['status'] != 'completed' or index.get('exit_status', 0) != 0:
        raise ValueError('Incomplete or unsuccessful benchmark evidence')
    if 'runs' in index:
        if index['status'] != 'completed' or not index['runs'] or len(index['runs']) != index.get('expected_repetitions', len(index['runs'])):
            raise ValueError('Incomplete benchmark suite')
        seen = set()
        for run in index['runs']:
            path = (root / run['path']).resolve()
            if not path.is_relative_to(root) or digest(path) != run['sha256']:
                raise ValueError('Changed or escaped suite run')
            if run['repetition'] in seen:
                raise ValueError('Duplicate repetition')
            seen.add(run['repetition'])
            audited = audit(path.parent)
            child = json.loads(path.read_text())
            if child['suite_id'] != index['suite_id'] or child['run_id'] != run['run_id'] or child['image_id'] != run['image_id']:
                raise ValueError('Mixed suite identity')
        return {'status': 'passed', 'runs': len(seen)}
    for name, sha in index['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path == root or digest(path) != sha:
            raise ValueError('Escaped or changed evidence: ' + name)
    required = ('identity.json', 'benchmark.json', 'server.log', 'quality/quality/summary.json',
                'quality/identity.json', 'gpu.csv', 'gpu-memory.json', 'telemetry.json')
    if any(name not in index['files'] for name in required):
        raise ValueError('Missing mandatory evidence')
    identity = json.loads((root / 'identity.json').read_text())
    for key in ('image_id', 'container_id', 'suite_id', 'run_id', 'repetition'):
        if identity[key] != index[key]:
            raise ValueError('Mixed evidence identity: ' + key)
    if identity['container']['Id'] != identity['container_id'] or 'sha256:' + identity['container']['Image'].removeprefix('sha256:') != 'sha256:' + identity['image_id'].removeprefix('sha256:'):
        raise ValueError('Wrong inspected container/image identity')
    report = json.loads((root / 'benchmark.json').read_text())
    if report.get('status', 'completed') != 'completed' or report['completed_exchanges'] != 10:
        raise ValueError('Conversation incomplete')
    if report['context_size'] != identity['props']['default_generation_settings']['n_ctx']:
        raise ValueError('Context mismatch')
    if not report['thinking_enabled'] or report['reasoning_effort'] != 'medium':
        raise ValueError('Wrong reasoning policy')
    argv = identity['argv']
    for flag, value in (('--ctx-size', str(report['context_size'])), ('--flash-attn', 'on'),
                        ('--cache-type-k', 'q8_0'), ('--cache-type-v', 'q8_0')):
        if flag not in argv or argv[argv.index(flag) + 1] != value:
            raise ValueError('Wrong effective runtime setting: ' + flag)
    if '--override-tensor' not in argv or argv[argv.index('--override-tensor') + 1] != '.*=CUDA0':
        raise ValueError('Language weights are not forced onto CUDA0')
    if '--no-mmproj-offload' not in argv:
        raise ValueError('Vision is not configured for CPU')
    stamp = datetime.datetime.fromisoformat(report['recorded_at'])
    captured = datetime.datetime.fromisoformat(identity['captured_at'])
    if not captured <= stamp or (stamp - captured).total_seconds() > 1200:
        raise ValueError('Stale benchmark timestamps')
    inputs = outputs = cached = thinking = decode_tokens = decode_ms = 0
    cache_known = thinking_known = timings_known = True
    for row in report['exchanges']:
        turn = row['exchange']
        response_path = f'benchmark/responses/turn-{turn:02d}.json'
        if response_path not in index['files']:
            raise ValueError('Missing checksummed response')
        response = json.loads((root / response_path).read_text())
        usage = response['usage']
        if response['choices'][0]['finish_reason'] != 'stop' or not response['choices'][0]['message'].get('reasoning_content'):
            raise ValueError('Missing/truncated reasoning')
        if row['prompt_tokens'] != usage['prompt_tokens'] or row['completion_tokens'] != usage['completion_tokens']:
            raise ValueError('Usage mismatch')
        inputs += usage['prompt_tokens']; outputs += usage['completion_tokens']
        hit = (response.get('timings') or {}).get('cache_n', (usage.get('prompt_tokens_details') or {}).get('cached_tokens'))
        if type(hit) is not int or not 0 <= hit <= usage['prompt_tokens']:
            hit = None
        if hit != row['cached_prompt_tokens']:
            raise ValueError('Cache counter mismatch')
        cache_known &= hit is not None
        cached += hit or 0
        count = row['reasoning_tokens']
        thinking_known &= count is not None
        thinking += count or 0
        real = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
        if row['reasoning_tokens_source'] == 'usage.completion_tokens_details.reasoning_tokens' and count != real:
            raise ValueError('Thinking counter mismatch')
        if row['reasoning_tokens_source'] == 'tokenizer.reasoning_content':
            token_path = f'benchmark/responses/thinking-{turn:02d}.json'
            if token_path not in index['files'] or len(json.loads((root / token_path).read_text())['tokens']) != count:
                raise ValueError('Thinking tokenizer evidence mismatch')
        request_path = f'benchmark/requests/turn-{turn:02d}.json'
        if request_path in index['files']:
            request = json.loads((root / request_path).read_text())
            if request['messages'] != report['messages'][:2 * turn - 1]:
                raise ValueError('Request/history mismatch')
            if request['reasoning_effort'] != 'medium' or request['chat_template_kwargs'] != {'enable_thinking': True, 'reasoning_effort': 'medium'}:
                raise ValueError('Request reasoning mismatch')
        else:
            raise ValueError('Missing actual request evidence')
        timing = response.get('timings') or {}
        n, ms = timing.get('predicted_n'), timing.get('predicted_ms')
        timings_known &= isinstance(n, (float, int)) and isinstance(ms, (float, int)) and n > 0 and ms > 0
        decode_tokens += n or 0; decode_ms += ms or 0
    expected = {'prompt_tokens': inputs, 'completion_tokens': outputs, 'total_tokens': inputs + outputs,
                'cached_prompt_tokens': cached if cache_known else None,
                'reasoning_tokens': thinking if thinking_known else None,
                'cache_hit_rate_percent': round(100 * cached / inputs, 2) if cache_known else None,
                'decode_tokens_per_second': round(decode_tokens / (decode_ms / 1000), 2) if timings_known else None,
                'output_tokens_per_wall_second': round(outputs / report['wall_seconds'], 2)}
    for key, value in expected.items():
        if not close_number(report[key], value):
            raise ValueError('Aggregate mismatch: ' + key)
    quality = json.loads((root / 'quality/quality/summary.json').read_text())
    quality_identity = json.loads((root / 'quality/identity.json').read_text())
    if quality_identity['container_id'] != identity['container_id'] or 'sha256:' + quality_identity['image_id'].removeprefix('sha256:') != 'sha256:' + identity['image_id'].removeprefix('sha256:') or quality_identity['suite_id'] != identity['suite_id']:
        raise ValueError('Quality identity mismatch')
    if len(quality['data']) != 9 or not all(row['passed'] for row in quality['data']):
        raise ValueError('Quality probes failed')
    import runpy
    summarize = runpy.run_path(str(Path(__file__).with_name('summarize-gpu-memory.py')))['summarize']
    zone = json.loads((root / 'telemetry.json').read_text())['timezone']
    computed = summarize(report, (root / 'gpu.csv').read_text(), zone)
    saved = json.loads((root / 'gpu-memory.json').read_text())
    for key in ('samples', 'mean_used_mib', 'peak_used_mib', 'minimum_used_mib'):
        if not close_number(saved[key], computed[key]):
            raise ValueError('VRAM mismatch: ' + key)
    return {'status': 'passed', 'image_id': identity['image_id'], **expected,
            'peak_used_mib': computed['peak_used_mib']}


if __name__ == '__main__':
    try:
        action, root = sys.argv[1:3]
        if action == 'capture':
            capture(root, *sys.argv[3:])
        elif action == 'finalize':
            finalize(root, *sys.argv[3:])
        elif action == 'suite':
            suite_index(root)
        elif action == 'audit':
            print(json.dumps(audit(root), indent=2))
        else:
            raise ValueError('Expected capture, finalize or audit')
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
