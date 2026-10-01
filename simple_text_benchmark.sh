#!/usr/bin/env bash
set -euo pipefail

# Simulate 10 user/assistant exchanges (20 messages), retaining full history.
# The ~16k target is cumulative API input + output, including repeated history.
if (( $# > 1 )); then
    echo 'Usage: ./simple_text_benchmark.sh [hostname[:port]]' >&2
    exit 2
fi
if (( $# == 1 )); then
    if [[ ! "$1" =~ ^([[:alnum:]_.-]+)(:([0-9]+))?$ ]]; then
        echo 'Error: expected hostname or hostname:port.' >&2
        exit 2
    fi
    hostname=${BASH_REMATCH[1]}
    port=${BASH_REMATCH[3]:-8080}
    if (( ${#port} > 5 )) || (( 10#$port < 1 || 10#$port > 65535 )); then
        echo 'Error: port must be between 1 and 65535.' >&2
        exit 2
    fi
    BONSAI_BASE_URL="http://$hostname:$port"
fi
export BONSAI_BASE_URL="${BONSAI_BASE_URL:-http://localhost:8080}"
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BONSAI_BENCHMARK_RESULT="${BONSAI_BENCHMARK_RESULT:-$project_dir/results/text-benchmark/$(date -u +%Y%m%dT%H%M%SZ)-$$.json}"

# Use only the Python standard library; never create bytecode caches.
python3 -B - <<'PY'
import sys
sys.dont_write_bytecode = True
import datetime
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

TARGET = 16000
TURNS = 10
MAX_OUTPUT = 128
base = os.environ['BONSAI_BASE_URL'].rstrip('/')
if base.endswith('/v1'):
    base = base[:-3]
result_path = Path(os.environ['BONSAI_BENCHMARK_RESULT'])
messages = []
records = []
# Related requests form a coherent conversation; answers are carried forward.
questions = [
    'Design a small community library. Describe its purpose and main users.',
    'Using that design, suggest a welcoming entrance and reading room.',
    'How should we arrange shelves and circulation paths in those rooms?',
    'Adapt our plan for wheelchair access and visitors with low vision.',
    'Add a quiet study zone without changing the earlier entrance plan.',
    'Choose practical lighting and ventilation for our planned spaces.',
    'Propose a simple borrowing workflow consistent with this library.',
    'Suggest three low-cost community activities for our existing layout.',
    'Review the decisions so far and identify the two largest risks.',
    'Summarize our agreed library plan and the next three implementation steps.',
]
filler = ('Planning note: preserve accessible paths, durable shelves, natural light, '
          'quiet spaces, and a modest maintenance budget.\n')


def call(path, payload=None):
    request = urllib.request.Request(
        base + path,
        data=None if payload is None else json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)


def prompt_tokens(candidate):
    # Render the same template/options as chat, then use the actual tokenizer.
    rendered = call('/apply-template', {
        'messages': candidate,
        'chat_template_kwargs': {'enable_thinking': False},
    })['prompt']
    return len(call('/tokenize', {
        'content': rendered, 'add_special': True, 'parse_special': True,
    })['tokens'])


def padded_question(question, desired_prompt):
    # Add neutral project notes to approach the budget without dropping history.
    def candidate(count):
        text = question + '\nRespond in about 70 words, using the previous decisions.'
        if count:
            text += '\nBackground planning notes:\n' + filler * count
        return messages + [{'role': 'user', 'content': text}]

    low, high = 0, TARGET // 8
    best = candidate(0)
    count = prompt_tokens(best)
    if count >= desired_prompt:
        return best, count
    while low < high:
        mid = (low + high + 1) // 2
        estimate = prompt_tokens(candidate(mid))
        if estimate <= desired_prompt:
            low = mid
        else:
            high = mid - 1
    best = candidate(low)
    return best, prompt_tokens(best)


def summary(elapsed):
    input_tokens = sum(row['prompt_tokens'] for row in records)
    output_tokens = sum(row['completion_tokens'] for row in records)
    # llama-server timings separate decoding from prompt processing and HTTP.
    decode_ms = sum(row['timings'].get('predicted_ms', 0) for row in records)
    decode_tokens = sum(row['timings'].get('predicted_n', 0) for row in records)
    has_decode_timings = bool(records) and all(
        row['timings'].get('predicted_ms', 0) > 0
        and row['timings'].get('predicted_n', 0) > 0 for row in records
    )
    total = input_tokens + output_tokens
    return {
        'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'base_url': base, 'model': 'bonsai2-27b',
        'message_count': len(messages), 'completed_exchanges': len(records),
        'target_tokens': TARGET, 'prompt_tokens': input_tokens,
        'completion_tokens': output_tokens, 'total_tokens': total,
        'within_5_percent': abs(total - TARGET) <= TARGET * 0.05,
        'accounting': 'Sum of chat API usage; repeated conversation history counts again.',
        'thinking_enabled': False, 'cache_prompt': True,
        'wall_seconds': round(elapsed, 3),
        'output_tokens_per_wall_second': round(output_tokens / elapsed, 2) if elapsed else None,
        'decode_tokens_per_second': round(decode_tokens / (decode_ms / 1000), 2)
        if has_decode_timings and decode_ms else None,
        'exchanges': records, 'messages': messages,
    }


def main():
    call('/health')
    props = call('/props')
    context = props['default_generation_settings']['n_ctx']
    print(f'Endpoint: {base}; context: {context}; target: {TARGET} cumulative tokens.', flush=True)
    started = time.monotonic()
    try:
        for turn, question in enumerate(questions, 1):
            remaining_turns = TURNS - turn + 1
            consumed = sum(row['prompt_tokens'] + row['completion_tokens'] for row in records)
            remaining = TARGET - consumed
            # Reserve future answers and prompt growth from retained conversation.
            # Recalculate after each measured response; the final turn uses the
            # remaining budget directly, allowing at most one short answer's drift.
            future_growth = MAX_OUTPUT + 100
            desired = int((remaining - MAX_OUTPUT * remaining_turns
                           - future_growth * remaining_turns * (remaining_turns - 1) / 2)
                          / remaining_turns)
            candidate, estimate = padded_question(question, max(1, desired))
            if estimate + MAX_OUTPUT > context:
                raise RuntimeError(f'Exchange {turn} needs {estimate + MAX_OUTPUT} context tokens; available: {context}')
            request_started = time.monotonic()
            response = call('/v1/chat/completions', {
                'model': 'bonsai2-27b', 'messages': candidate,
                'temperature': 0, 'max_tokens': MAX_OUTPUT, 'cache_prompt': True,
                'chat_template_kwargs': {'enable_thinking': False},
            })
            seconds = time.monotonic() - request_started
            usage = response['usage']
            for key in ('prompt_tokens', 'completion_tokens'):
                if type(usage.get(key)) is not int or usage[key] < 1:
                    raise RuntimeError(f'Missing or invalid API usage: {usage}')
            assistant = response['choices'][0]['message']['content']
            if not isinstance(assistant, str) or not assistant.strip():
                raise RuntimeError('The API returned an empty assistant response.')
            messages[:] = candidate + [{'role': 'assistant', 'content': assistant}]
            records.append({
                'exchange': turn, 'prompt_tokens': usage['prompt_tokens'],
                'completion_tokens': usage['completion_tokens'],
                'estimated_prompt_tokens': estimate, 'wall_seconds': round(seconds, 3),
                'finish_reason': response['choices'][0].get('finish_reason'),
                'timings': response.get('timings') or {},
            })
            print(f'\nMessage {2 * turn - 1}/20 (user): {question}', flush=True)
            print(f'Message {2 * turn}/20 (assistant): {assistant}', flush=True)
            print(f"Usage: {usage['prompt_tokens']} input + {usage['completion_tokens']} output; "
                  f'{seconds:.2f}s.', flush=True)
    finally:
        # Preserve partial evidence if a later request fails.
        report = summary(time.monotonic() - started)
        report['context_size'] = context
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        visible = {key: value for key, value in report.items() if key not in ('messages', 'exchanges')}
        print('\n' + json.dumps(visible, ensure_ascii=False, indent=2), flush=True)
        print(f'Report: {result_path}', flush=True)
    if not report['within_5_percent']:
        raise RuntimeError('Measured token total missed the 16k target by more than 5%; see the report.')


try:
    main()
except (urllib.error.URLError, KeyError, ValueError, RuntimeError, OSError) as error:
    print(f'Benchmark failed: {error}', file=sys.stderr)
    sys.exit(1)
PY
