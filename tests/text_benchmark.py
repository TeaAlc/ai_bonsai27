#!/usr/bin/env -S python3 -B
"""Medium-reasoning conversation benchmark; public CLI: simple_text_benchmark.sh."""
import sys
sys.dont_write_bytecode = True
import datetime
import json
import os
import time
import signal
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from api_http import urlopen

TARGET = 16000
TURNS = 10
MAX_OUTPUT = 4096
OUTPUT_RESERVE = 512
base = os.environ['BONSAI_BASE_URL'].rstrip('/')
if base.endswith('/v1'):
    base = base[:-3]
result_path = Path(os.environ['BONSAI_BENCHMARK_RESULT'])
messages = []
records = []
run_status = 'running'
run_error = None
started_at = None
deadline = None
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
    remaining = 600 if deadline is None else deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Conversation deadline exceeded')
    if path == '/v1/chat/completions':
        directory = result_path.with_suffix('') / 'requests'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'turn-{len(records) + 1:02d}.json').write_text(json.dumps(payload, indent=2) + '\n')
    with urlopen(request, timeout=min(600, remaining)) as response:
        answer = json.load(response)
    if path == '/v1/chat/completions':
        directory = result_path.with_suffix('') / 'responses'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'turn-{len(records) + 1:02d}.json').write_text(json.dumps(answer, indent=2) + '\n')
    return answer


def prompt_tokens(candidate):
    # Render the same template/options as chat, then use the actual tokenizer.
    rendered = call('/apply-template', {
        'messages': candidate,
        'chat_template_kwargs': {'enable_thinking': True, 'reasoning_effort': 'medium'},
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


def cache_metrics(response):
    # Count reused input tokens, not requests with any hit or generated tokens.
    # Missing counters mean unknown; never report them as a zero-hit cache.
    usage = response['usage']
    timings = response.get('timings') or {}
    details = usage.get('prompt_tokens_details') or {}
    if 'cache_n' in timings:
        cached = timings['cache_n']
        source = 'timings.cache_n'
    else:
        cached = details.get('cached_tokens')
        source = 'usage.prompt_tokens_details.cached_tokens'
    total = usage['prompt_tokens']
    valid = type(cached) is int and 0 <= cached <= total
    return {
        'cached_prompt_tokens': cached if valid else None,
        'processed_prompt_tokens': total - cached if valid else None,
        'cache_hit_rate_percent': round(100 * cached / total, 2) if valid else None,
        'cache_metrics_source': source if valid else None,
    }


def reasoning_metrics(response, reasoning):
    # Prefer actual API accounting. This backend may omit its reasoning counter;
    # retokenizing decoded thinking then gives a count with boundary uncertainty.
    details = response['usage'].get('completion_tokens_details') or {}
    tokens = details.get('reasoning_tokens')
    if type(tokens) is int and 0 <= tokens <= response['usage']['completion_tokens']:
        return {'reasoning_tokens': tokens,
                'reasoning_tokens_source': 'usage.completion_tokens_details.reasoning_tokens',
                'reasoning_tokens_are_estimated': False}
    try:
        tokenized = call('/tokenize', {
            'content': reasoning, 'add_special': False, 'parse_special': False,
        })
        evidence = result_path.with_suffix('') / 'responses' / f'thinking-{len(records) + 1:02d}.json'
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(tokenized, indent=2) + '\n')
        encoded = tokenized['tokens']
        if not isinstance(encoded, list):
            raise ValueError('Invalid tokenizer response')
        return {'reasoning_tokens': len(encoded),
                'reasoning_tokens_source': 'tokenizer.reasoning_content',
                'reasoning_tokens_are_estimated': True}
    except (urllib.error.URLError, KeyError, ValueError, OSError):
        return {'reasoning_tokens': None, 'reasoning_tokens_source': None,
                'reasoning_tokens_are_estimated': None}


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
    cache_exchanges = sum(row['cached_prompt_tokens'] is not None for row in records)
    complete_cache_metrics = bool(records) and cache_exchanges == len(records)
    cached_tokens = sum(row['cached_prompt_tokens'] or 0 for row in records)
    total = input_tokens + output_tokens
    return {
        'schema_version': 1, 'status': run_status, 'error': run_error,
        'evidence_scope': 'API-only', 'started_at': started_at,
        'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'base_url': base, 'model': 'bonsai2-27b',
        'message_count': len(messages), 'completed_exchanges': len(records),
        'target_tokens': TARGET, 'prompt_tokens': input_tokens,
        'completion_tokens': output_tokens, 'total_tokens': total,
        'within_5_percent': abs(total - TARGET) <= TARGET * 0.05,
        'accounting': 'Sum of chat API usage; repeated conversation history counts again.',
        'thinking_enabled': True, 'reasoning_effort': 'medium',
        'maximum_completion_tokens': MAX_OUTPUT, 'output_budget_reserve': OUTPUT_RESERVE,
        'reasoning_characters': sum(row['reasoning_characters'] for row in records),
        'reasoning_tokens': sum(row['reasoning_tokens'] for row in records)
        if records and all(row['reasoning_tokens'] is not None for row in records) else None,
        'reasoning_metrics_exchanges': sum(row['reasoning_tokens'] is not None for row in records),
        'reasoning_tokens_are_estimated': any(row['reasoning_tokens_are_estimated'] for row in records)
        if records and all(row['reasoning_tokens'] is not None for row in records) else None,
        'cache_prompt': True,
        'cache_metrics_exchanges': cache_exchanges,
        'cached_prompt_tokens': cached_tokens if complete_cache_metrics else None,
        'processed_prompt_tokens': input_tokens - cached_tokens if complete_cache_metrics else None,
        'cache_hit_rate_percent': round(100 * cached_tokens / input_tokens, 2)
        if complete_cache_metrics else None,
        'cache_hit_rate_definition': '100 * sum(cached prompt tokens) / sum(all prompt tokens), including the first request.',
        'wall_seconds': round(elapsed, 3),
        'output_tokens_per_wall_second': round(output_tokens / elapsed, 2) if elapsed else None,
        'decode_tokens_per_second': round(decode_tokens / (decode_ms / 1000), 2)
        if has_decode_timings and decode_ms else None,
        'exchanges': records, 'messages': messages,
    }


def atomic_report(report):
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=result_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(temporary, result_path)


def main():
    global run_status, run_error, started_at, deadline
    # Reserve a unique output directory before sending requests. Never replace
    # another conversation's response files, including an interrupted run.
    result_path.parent.mkdir(parents=True, exist_ok=True)
    if result_path.exists():
        raise RuntimeError('Result already exists; choose another BONSAI_BENCHMARK_RESULT.')
    result_path.with_suffix('').mkdir(exist_ok=False)
    started = time.monotonic()
    deadline = started + 600
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    context = None
    try:
        call('/health')
        props = call('/props')
        context = props['default_generation_settings']['n_ctx']
        print(f'Endpoint: {base}; context: {context}; target: {TARGET} cumulative tokens; '
              f'thinking: enabled; reasoning: medium; completion cap: {MAX_OUTPUT}.', flush=True)
        for turn, question in enumerate(questions, 1):
            remaining_turns = TURNS - turn + 1
            consumed = sum(row['prompt_tokens'] + row['completion_tokens'] for row in records)
            remaining = TARGET - consumed
            # Reserve typical reasoning output separately from its hard completion cap.
            # Only final answers are replayed, so visible history grows more slowly.
            # Recalculate after each measured response; the final turn uses the
            # remaining budget directly; complete reasoning can still exceed the target.
            future_growth = 128 + 100
            desired = int((remaining - OUTPUT_RESERVE * remaining_turns
                           - future_growth * remaining_turns * (remaining_turns - 1) / 2)
                          / remaining_turns)
            candidate, estimate = padded_question(question, max(1, desired))
            if estimate + MAX_OUTPUT > context:
                raise RuntimeError(f'Exchange {turn} needs {estimate + MAX_OUTPUT} context tokens; available: {context}')
            request_started = time.monotonic()
            response = call('/v1/chat/completions', {
                'model': 'bonsai2-27b', 'messages': candidate,
                'temperature': 0, 'max_tokens': MAX_OUTPUT, 'cache_prompt': True,
                'reasoning_effort': 'medium',
                'chat_template_kwargs': {'enable_thinking': True, 'reasoning_effort': 'medium'},
            })
            seconds = time.monotonic() - request_started
            usage = response['usage']
            for key in ('prompt_tokens', 'completion_tokens'):
                if type(usage.get(key)) is not int or usage[key] < 1:
                    raise RuntimeError(f'Missing or invalid API usage: {usage}')
            result_path.parent.mkdir(parents=True, exist_ok=True)
            response_dir = result_path.with_suffix('') / 'responses'
            response_dir.mkdir(parents=True, exist_ok=True)
            (response_dir / f'turn-{turn:02d}.json').write_text(json.dumps(response, indent=2) + '\n')
            assistant = response['choices'][0]['message']['content']
            reasoning = response['choices'][0]['message'].get('reasoning_content') or ''
            if not isinstance(reasoning, str) or not reasoning.strip():
                raise RuntimeError('No reasoning content returned with thinking enabled.')
            if response['choices'][0].get('finish_reason') != 'stop':
                raise RuntimeError('Reasoning response was truncated.')
            if not isinstance(assistant, str) or not assistant.strip():
                raise RuntimeError('The API returned an empty assistant response.')
            messages[:] = candidate + [{'role': 'assistant', 'content': assistant}]
            cache = cache_metrics(response)
            thinking = reasoning_metrics(response, reasoning)
            records.append({
                'reasoning_characters': len(reasoning),
                'exchange': turn, 'prompt_tokens': usage['prompt_tokens'],
                'completion_tokens': usage['completion_tokens'],
                'estimated_prompt_tokens': estimate, 'wall_seconds': round(seconds, 3),
                'finish_reason': response['choices'][0].get('finish_reason'),
                'timings': response.get('timings') or {},
                **cache, **thinking,
            })
            # Color only message labels, using the same terminal policy as statistics.
            use_color = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
            user_label = f'Message {2 * turn - 1}/20 (user):'
            assistant_label = f'Message {2 * turn}/20 (assistant):'
            if use_color:
                user_label = f'\033[1;33m{user_label}\033[0m'
                assistant_label = f'\033[1;32m{assistant_label}\033[0m'
            print(f'\n{user_label} {question}', flush=True)
            print(f'{assistant_label} {assistant}', flush=True)
            reasoning_count = thinking['reasoning_tokens']
            reasoning_display = 'unknown' if reasoning_count is None else str(reasoning_count)
            if thinking['reasoning_tokens_are_estimated']:
                reasoning_display += ' (est.)'
            if cache['cached_prompt_tokens'] is None:
                cache_display = 'unknown; hit rate unknown'
            else:
                cache_display = (f"{cache['cached_prompt_tokens']} cached + "
                                 f"{cache['processed_prompt_tokens']} processed; "
                                 f"hit rate {cache['cache_hit_rate_percent']:.2f}%")
            metrics = (f"Tokens: {usage['prompt_tokens']} in | {usage['completion_tokens']} out "
                       f"(incl. {reasoning_display} reasoning) | "
                       f"Cache: {cache_display} | {seconds:.2f}s")
            # Highlight terminal output; keep redirected logs free of ANSI escapes.
            if use_color:
                metrics = f'\033[1;36m{metrics}\033[0m'
            print(metrics, flush=True)
        run_status = 'completed'
    except BaseException as error:
        run_status = 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed'
        if isinstance(error, TimeoutError):
            run_status = 'timed-out'
        run_error = str(error) or type(error).__name__
        raise
    finally:
        # Preserve partial evidence if a later request fails.
        report = summary(time.monotonic() - started)
        report['context_size'] = context
        result_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_report(report)
        visible = {key: value for key, value in report.items() if key not in ('messages', 'exchanges')}
        print('\n' + json.dumps(visible, ensure_ascii=False, indent=2), flush=True)
        print(f'Report: {result_path}', flush=True)
    # A usage-budget deviation is reported, not treated as an inference failure.
    if not report['within_5_percent']:
        print('Warning: cumulative API usage is outside the approximate 16k target (plus/minus 5%); report preserves actual usage.', file=sys.stderr)


def cancel(_signal, _frame):
    raise KeyboardInterrupt('Termination requested')


def cli():
    signal.signal(signal.SIGTERM, cancel)
    try:
        main()
    except KeyboardInterrupt as error:
        print(f'Benchmark cancelled: {error}', file=sys.stderr)
        return 130
    except (urllib.error.URLError, KeyError, ValueError, RuntimeError, OSError) as error:
        print(f'Benchmark failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(cli())
