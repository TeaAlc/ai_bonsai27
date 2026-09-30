#!/usr/bin/env -S python3 -B
"""Audit one identified live test run and its explicitly related 8k run."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import re
from pathlib import Path


def audit(directory):
    root = Path(directory)
    identity = json.loads((root / 'identity.json').read_text())
    small = json.loads((root / 'context-8192/identity.json').read_text())
    def read(name, folder=root, metadata=identity):
        envelope = json.loads((folder / (name + '.json')).read_text())
        if envelope['run_id'] != metadata['run_id'] or envelope['image_id'] != metadata['image_id']:
            raise ValueError('mixed or stale test evidence')
        if envelope['recorded_at'] < metadata['started_at']:
            raise ValueError('evidence predates this test run')
        return envelope['data']
    log = (root / 'server.log').read_text()
    if any(identity[key] != small[key] for key in ('image_id', 'revision', 'suite_id', 'model_hashes')):
        raise ValueError('8k and 16k checks use different images')
    if read('server-log')['sha256'] != hashlib.sha256((root / 'server.log').read_bytes()).hexdigest():
        raise ValueError('server log does not belong to this evidence set')
    models = read('models')
    chat = read('chat')
    vision = read('vision/summary')
    coding = read('coding/summary')
    props8 = read('props', root / 'context-8192', small)
    checks = {
        'all_layers_cuda': 'offloaded 66/66 layers to GPU' in log,
        'all_model_buffers_cuda': bool(re.search(r'CUDA0 model buffer size', log)) and not re.search(r'(?:CPU|CPU_Mapped|CUDA_Host)\s+model buffer size', log),
        'flash_attention_main_and_mtp': log.count('flash_attn            = enabled') >= 2,
        'q8_main_and_mtp': len(re.findall(r'K \(q8_0\).*V \(q8_0\)', log)) >= 2,
        'mtp_n2': 'n_max=2,' in log and 'speculative decoding enabled: draft-mtp' in log,
        'gpu_draft': 'devices=[CUDA0]' in log,
        'no_cuda_init_error': 'failed to initialize CUDA' not in log,
        'context_16k': identity['context'] == 16384 and read('props')['default_generation_settings']['n_ctx'] == 16384,
        'context_env_8k': small['context'] == 8192 and props8['default_generation_settings']['n_ctx'] == 8192,
        'pinned_models': [line.split()[0] for line in identity['model_hashes']] == ['1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685', 'e287342d92332fa3577ed1d42e921dac9370c08da58ba9337fa450f6cc76cfd7'],
        'api_model': any(item['id'] == 'bonsai2-27b' for item in models['data']),
        'api_chat': chat['choices'][0]['message']['content'].strip() == '42',
        'api_long_context': read('api-test-summary')['long_context_pass'] and read('context-16k')['usage']['prompt_tokens'] >= 14900,
        'vision_cpu_backend': 'CLIP using CPU backend' in log,
        'vision_bf16_projector': 'Ternary-Bonsai-2-27B-mmproj-BF16.gguf' in log,
        'vision_api_pass': len(vision) == 2 and all(item['passed'] for item in vision),
        'mtp_api_drafting': any(item.get('timings', {}).get('draft_n', 0) > 0 and 0 <= item['timings'].get('draft_n_accepted', -1) <= item['timings']['draft_n'] for item in coding),
        'coding_all_pass': len(coding) == 3 and all(item['passed'] for item in coding),
    }
    (root / 'qa-summary.json').write_text(json.dumps(checks, indent=2) + '\n')
    if not all(checks.values()): raise AssertionError(checks)
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory')
    print(json.dumps(audit(parser.parse_args().run_directory), indent=2))
