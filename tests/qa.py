#!/usr/bin/env -S python3 -B
"""Audit one identified live test run and its explicitly related 8k run."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
import re
import subprocess
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
    # Verbose token logs can contain individual bytes of a UTF-8 token.
    # Decode only for ASCII runtime checks; bind evidence to the untouched bytes.
    log_bytes = (root / 'server.log').read_bytes()
    log = log_bytes.decode('utf-8', errors='replace')
    if any(identity[key] != small[key] for key in ('image_id', 'revision', 'suite_id', 'model_hashes')):
        raise ValueError('8k and 16k checks use different images')
    model_variant = identity.get('model_variant', 'ptq1_0')
    if model_variant != small.get('model_variant', 'ptq1_0'):
        raise ValueError('8k and 16k checks use different model variants')
    if model_variant not in ('ptq1_0', 'pq2_0'):
        raise ValueError('Unsupported model variant in test evidence')
    # Use shared pins for the identified variant; never accept an arbitrary hash.
    pins = Path(__file__).resolve().parents[1] / 'data/models/download.sh'
    expected_hashes = subprocess.check_output([
        'bash', '-c', 'set -e; source "$1"; printf "%s\\n" "$MODEL_SHA" "$VISION_SHA"',
        'qa-model-pins', str(pins),
    ], env=dict(os.environ, BONSAI_MODEL_VARIANT=model_variant), text=True).splitlines()
    image_pin_matches = identity.get('model_pin_sha256') in (None, expected_hashes[0])
    image_pin_matches = image_pin_matches and small.get('model_pin_sha256') in (None, expected_hashes[0])
    if read('server-log')['sha256'] != hashlib.sha256(log_bytes).hexdigest():
        raise ValueError('server log does not belong to this evidence set')
    models = read('models')
    chat = read('chat')
    vision = read('vision/summary')
    coding = read('coding/summary')
    props8 = read('props', root / 'context-8192', small)
    # The published Ada bundle and newer Prism server report initialization
    # differently. Both forms must identify an actually initialized MTP strategy.
    mtp_initialized = ('speculative decoding enabled: draft-mtp' in log or
                       ("adding speculative implementation 'draft-mtp'" in log and
                        'speculative decoding context initialized' in log))
    checks = {
        'all_layers_cuda': 'offloaded 66/66 layers to GPU' in log,
        'all_model_buffers_cuda': bool(re.search(r'CUDA0 model buffer size', log)) and not re.search(r'(?:CPU|CPU_Mapped|CUDA_Host)\s+model buffer size', log),
        'flash_attention_main_and_mtp': log.count('flash_attn            = enabled') >= 2,
        'q8_main_and_mtp': len(re.findall(r'K \(q8_0\).*V \(q8_0\)', log)) >= 2,
        'mtp_n2': 'n_max=2,' in log and mtp_initialized,
        'gpu_draft': 'devices=[CUDA0]' in log,
        'no_cuda_init_error': 'failed to initialize CUDA' not in log,
        'context_16k': identity['context'] == 16384 and read('props')['default_generation_settings']['n_ctx'] == 16384,
        'context_env_8k': small['context'] == 8192 and props8['default_generation_settings']['n_ctx'] == 8192,
        'pinned_models': image_pin_matches and [line.split()[0] for line in identity['model_hashes']] == expected_hashes,
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
