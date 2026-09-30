#!/usr/bin/env -S python3 -B
"""Validate model identity, arithmetic, and recall across a ~15k-token prompt."""
import sys
sys.dont_write_bytecode = True
import json
import os
import time
from api_support import call, save, wait_ready, identity

wait_ready()
identity()
context_size = int(os.environ.get('BONSAI_CTX_SIZE', '16384'))
if context_size < 16384:
    raise ValueError('Long-context validation requires at least 16384 tokens')
models = call('/v1/models')
save('models', models)
assert any(model['id'] == 'bonsai2-27b' for model in models['data'])
props = call('/props')
save('props', props)
assert props['default_generation_settings']['n_ctx'] == context_size, props

started = time.monotonic()
chat = call('/v1/chat/completions', {
    'model': 'bonsai2-27b',
    'messages': [{'role': 'user', 'content': 'Reply with only the number: What is 19 + 23?'}],
    'temperature': 0, 'max_tokens': 256,
    'chat_template_kwargs': {'enable_thinking': False},
})
save('chat', chat)
assert chat['choices'][0]['message']['content'].strip() == '42', chat
print('Chat:', chat['choices'][0]['message']['content'],
      'seconds:', round(time.monotonic() - started, 2), flush=True)

# Binary search the actual tokenizer so the filler exercises the context window
# without depending on an estimate of tokens per word.
prefix = 'Remember the secret marker BONSAI-CEDAR-7429.\n'
suffix = '\nQuestion: What is the secret marker mentioned at the beginning? Answer only the marker.\nAnswer:'
unit = 'This is a neutral filler sentence about trees, leaves, roots and seasons.\n'
low, high = 0, 2000
while low < high:
    count = (low + high + 1) // 2
    token_count = len(call('/tokenize', {
        'content': prefix + unit * count + suffix, 'add_special': True,
    })['tokens'])
    if token_count <= 15000:
        low = count
    else:
        high = count - 1
prompt = prefix + unit * low + suffix
count = len(call('/tokenize', {'content': prompt, 'add_special': True})['tokens'])
assert 14900 <= count <= 15000, count
started = time.monotonic()
response = call('/v1/chat/completions', {
    'model': 'bonsai2-27b', 'messages': [{'role': 'user', 'content': prompt}],
    'temperature': 0, 'max_tokens': 128, 'cache_prompt': False,
    'chat_template_kwargs': {'enable_thinking': False},
})
elapsed = time.monotonic() - started
save('context-16k', response)
assert response['usage']['prompt_tokens'] >= 14900, response
assert 'BONSAI-CEDAR-7429' in response['choices'][0]['message']['content'], response
summary = {'context_window': context_size, 'long_prompt_tokens': count,
           'long_wall_seconds': elapsed, 'long_usage': response['usage'],
           'timings': response.get('timings'), 'chat_pass': True, 'long_context_pass': True}
save('api-test-summary', summary)
print(json.dumps(summary, indent=2), flush=True)
