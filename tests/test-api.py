#!/usr/bin/env -S python3 -B

# Keep imports from writing bytecode caches, including when run via python3.
import sys
sys.dont_write_bytecode = True

import json, os, time, urllib.request
from pathlib import Path
base = os.environ.get('BONSAI_BASE_URL', 'http://127.0.0.1:8080')
out = Path(__file__).resolve().parent.parent / 'results'; out.mkdir(exist_ok=True)
def call(path, data=None):
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)
def save(name, data):
    (out / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2))
for _ in range(180):
    try:
        call('/health'); break
    except Exception:
        time.sleep(2)
else:
    raise RuntimeError('Server is not ready')
models = call('/v1/models'); save('models', models)
assert any(m['id'] == 'bonsai2-27b' for m in models['data'])
props = call('/props'); save('props', props)
assert props['default_generation_settings']['n_ctx'] == int(os.environ.get('BONSAI_CTX_SIZE', '16384')), props
start = time.monotonic()
chat = call('/v1/chat/completions', {'model': 'bonsai2-27b', 'messages': [{'role': 'user', 'content': 'Reply with only the number: What is 19 + 23?'}], 'temperature': 0, 'max_tokens': 256, 'chat_template_kwargs': {'enable_thinking': False}})
save('chat', chat)
assert '42' in chat['choices'][0]['message']['content'], chat
print('Chat:', chat['choices'][0]['message']['content'], 'seconds:', round(time.monotonic()-start, 2), flush=True)
prefix = 'Remember the secret marker BONSAI-CEDAR-7429.\n'
suffix = '\nQuestion: What is the secret marker mentioned at the beginning? Answer only the marker.\nAnswer:'
unit = 'This is a neutral filler sentence about trees, leaves, roots and seasons.\n'
lo, hi = 0, 2000
while lo < hi:
    n = (lo + hi + 1) // 2
    count = len(call('/tokenize', {'content': prefix + unit*n + suffix, 'add_special': True})['tokens'])
    if count <= 15000: lo = n
    else: hi = n-1
prompt = prefix + unit*lo + suffix
count = len(call('/tokenize', {'content': prompt, 'add_special': True})['tokens'])
assert 14900 <= count <= 15000, count
start = time.monotonic()
long = call('/v1/chat/completions', {'model': 'bonsai2-27b', 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0, 'max_tokens': 128, 'cache_prompt': False, 'chat_template_kwargs': {'enable_thinking': False}})
elapsed = time.monotonic()-start
save('context-16k', long)
assert long['usage']['prompt_tokens'] >= 14900, long
assert 'BONSAI-CEDAR-7429' in long['choices'][0]['message']['content'], long
summary = {'context_window': int(os.environ.get('BONSAI_CTX_SIZE', '16384')), 'long_prompt_tokens': count, 'long_wall_seconds': elapsed, 'long_usage': long['usage'], 'timings': long.get('timings'), 'chat_pass': True, 'long_context_pass': True}
save('api-test-summary', summary)
print(json.dumps(summary, indent=2), flush=True)
