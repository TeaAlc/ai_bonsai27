#!/usr/bin/env -S python3 -B
"""Exercise the real benchmark against a deterministic local HTTP fixture."""
import sys
sys.dont_write_bytecode = True
import json
import os
import signal
import time
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='text-benchmark-', dir='/tmp/bonsai27')
        self.addCleanup(self.work.cleanup)
        self.requests = []
        self.context = 16384
        self.fail_chat = False
        self.delay_chat = False
        self.cache_mode = 'timings'
        self.missing_reasoning = False
        self.truncated = False
        self.large_output = False
        self.api_reasoning_counter = False
        self.unavailable_reasoning_tokens = False
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, value, status=200):
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:
                    pass  # Cancellation intentionally closes this fixture socket.

            def do_GET(self):
                if self.path == '/health':
                    self.reply({'status': 'ok'})
                elif self.path == '/props':
                    self.reply({'default_generation_settings': {'n_ctx': fixture.context}})
                else:
                    self.reply({}, 404)

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path == '/apply-template':
                    self.reply({'prompt': ' '.join(message['content'] for message in payload['messages'])})
                elif self.path == '/tokenize':
                    if fixture.unavailable_reasoning_tokens and payload.get('parse_special') is False:
                        self.reply({'error': 'Tokenizer unavailable'}, 503)
                        return
                    self.reply({'tokens': list(range(len(payload['content'].split())))})
                elif self.path == '/v1/chat/completions':
                    if fixture.fail_chat:
                        self.reply({'error': 'Fixture failure'}, 503)
                        return
                    fixture.requests.append(payload)
                    if fixture.delay_chat:
                        time.sleep(2)
                    turn = len(fixture.requests)
                    answer = f'Exchange {turn}: retain the accessible entrance, quiet study area and durable library shelving.'
                    output_tokens = 2000 if fixture.large_output else len(answer.split()) + 2
                    prompt_tokens = sum(len(message['content'].split()) for message in payload['messages'])
                    cached = 0 if turn == 1 else prompt_tokens * 3 // 4
                    result = {
                        'usage': {'prompt_tokens': prompt_tokens,
                                  'completion_tokens': output_tokens},
                        'choices': [{'message': {'content': answer,
                                                 'reasoning_content': '' if fixture.missing_reasoning else 'Plan carefully.'},
                                     'finish_reason': 'length' if fixture.truncated else 'stop'}],
                        'timings': {'predicted_n': output_tokens, 'predicted_ms': output_tokens * 20},
                    }
                    if fixture.api_reasoning_counter:
                        result['usage']['completion_tokens_details'] = {'reasoning_tokens': 2}
                    if fixture.cache_mode == 'timings':
                        result['timings'].update(cache_n=cached, prompt_n=prompt_tokens - cached)
                    elif fixture.cache_mode == 'usage':
                        result['usage']['prompt_tokens_details'] = {'cached_tokens': cached}
                    elif fixture.cache_mode == 'zero':
                        result['timings']['cache_n'] = 0
                    elif fixture.cache_mode == 'partial' and turn != 2:
                        result['timings']['cache_n'] = cached
                    elif fixture.cache_mode == 'invalid':
                        result['timings']['cache_n'] = prompt_tokens + 1
                    self.reply(result)
                else:
                    self.reply({}, 404)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def invoke(self, argument=None, base_suffix=''):
        result_path = Path(self.work.name) / f'report-{len(list(Path(self.work.name).glob("*.json")))}.json'
        environment = dict(os.environ, http_proxy='http://127.0.0.1:1', HTTP_PROXY='http://127.0.0.1:1',
                           no_proxy='', NO_PROXY='', BONSAI_BASE_URL=f'http://127.0.0.1:{self.server.server_port}{base_suffix}',
                           BONSAI_BENCHMARK_RESULT=str(result_path))
        args = ['bash', str(PROJECT / 'simple_text_benchmark.sh')]
        if argument is not None:
            args.append(argument)
        process = subprocess.run(args, env=environment, text=True, capture_output=True, timeout=60)
        return process, json.loads(result_path.read_text()) if result_path.exists() else None

    def test_conversation_and_budget(self):
        process, report = self.invoke(base_suffix='/v1')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['message_count'], 20)
        self.assertEqual(report['completed_exchanges'], 10)
        self.assertTrue(report['within_5_percent'])
        self.assertEqual(report['reasoning_tokens'], 20)
        self.assertTrue(report['reasoning_tokens_are_estimated'])
        self.assertEqual(report['total_tokens'], report['prompt_tokens'] + report['completion_tokens'])
        self.assertEqual(report['decode_tokens_per_second'], 50)
        self.assertEqual(len(self.requests), 10)
        for index, payload in enumerate(self.requests):
            self.assertEqual(len(payload['messages']), index * 2 + 1)
            self.assertEqual(payload['messages'], report['messages'][:index * 2 + 1])
            self.assertEqual(payload['max_tokens'], 4096)
            self.assertEqual(payload['reasoning_effort'], 'medium')
            self.assertEqual(payload['chat_template_kwargs']['reasoning_effort'], 'medium')
            self.assertTrue(payload['chat_template_kwargs']['enable_thinking'])
        self.assertIn('Message 20/20', process.stdout)
        cached = sum(row['cached_prompt_tokens'] for row in report['exchanges'])
        self.assertEqual(report['cached_prompt_tokens'], cached)
        self.assertEqual(report['processed_prompt_tokens'], report['prompt_tokens'] - cached)
        self.assertEqual(report['cache_hit_rate_percent'], round(100 * cached / report['prompt_tokens'], 2))
        self.assertEqual(report['cache_metrics_exchanges'], 10)
        self.assertEqual(report['exchanges'][0]['cache_hit_rate_percent'], 0)
        self.assertNotIn('\033[', process.stdout)
        self.assertNotIn('Thinking tokens:', process.stdout)
        self.assertNotIn('Usage:', process.stdout)
        cache_lines = [line for line in process.stdout.splitlines() if line.startswith('Tokens:')]
        self.assertEqual(len(cache_lines), 10)
        for line, row in zip(cache_lines, report['exchanges']):
            self.assertIn('(+2 (est.) reasoning) | Cache:', line)
            self.assertIn(f"Tokens: {row['prompt_tokens']} in | "
                          f"{row['completion_tokens'] - row['reasoning_tokens']} out", line)

    def test_prefers_actual_api_reasoning_counter(self):
        self.api_reasoning_counter = True
        process, report = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['reasoning_tokens'], 20)
        self.assertFalse(report['reasoning_tokens_are_estimated'])
        self.assertIn('(+2 reasoning) | Cache:', process.stdout)
        for row in report['exchanges']:
            self.assertIn(f"Tokens: {row['prompt_tokens']} in | "
                          f"{row['completion_tokens'] - row['reasoning_tokens']} out (+2 reasoning)",
                          process.stdout)
        self.assertEqual(report['exchanges'][0]['reasoning_tokens_source'],
                         'usage.completion_tokens_details.reasoning_tokens')

    def test_unavailable_thinking_count_remains_unknown(self):
        self.unavailable_reasoning_tokens = True
        process, report = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIsNone(report['reasoning_tokens'])
        self.assertEqual(report['reasoning_metrics_exchanges'], 0)
        self.assertIsNone(report['reasoning_tokens_are_estimated'])
        self.assertIn('unknown out (+unknown reasoning) | Cache:', process.stdout)

    def test_missing_reasoning_is_not_a_valid_benchmark(self):
        self.missing_reasoning = True
        process, report = self.invoke()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report['completed_exchanges'], 0)
        self.assertIn('No reasoning content', process.stderr)

    def test_truncated_reasoning_is_rejected(self):
        self.truncated = True
        process, report = self.invoke()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report['completed_exchanges'], 0)
        self.assertIn('truncated', process.stderr)

    def test_complete_reasoning_can_exceed_usage_budget(self):
        self.large_output = True
        process, report = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['completed_exchanges'], 10)
        self.assertFalse(report['within_5_percent'])
        self.assertIn('Warning:', process.stderr)

    def test_usage_cache_counter_fallback(self):
        self.cache_mode = 'usage'
        process, report = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertGreater(report['cache_hit_rate_percent'], 0)
        self.assertEqual(report['exchanges'][1]['cache_metrics_source'],
                         'usage.prompt_tokens_details.cached_tokens')

    def test_unknown_cache_counters_are_not_zero(self):
        for mode, available in [('missing', 0), ('partial', 9), ('invalid', 0)]:
            with self.subTest(mode=mode):
                self.cache_mode = mode
                self.requests.clear()
                process, report = self.invoke()
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertIsNone(report['cached_prompt_tokens'])
                self.assertIsNone(report['processed_prompt_tokens'])
                self.assertIsNone(report['cache_hit_rate_percent'])
                self.assertEqual(report['cache_metrics_exchanges'], available)
                self.assertIn('hit rate unknown', process.stdout)

    def test_actual_zero_cache_hits(self):
        self.cache_mode = 'zero'
        process, report = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['cached_prompt_tokens'], 0)
        self.assertEqual(report['processed_prompt_tokens'], report['prompt_tokens'])
        self.assertEqual(report['cache_hit_rate_percent'], 0)

    def test_explicit_hostname_overrides_environment(self):
        process, report = self.invoke(f'127.0.0.1:{self.server.server_port}')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(report['within_5_percent'])

    def test_context_rejected_before_inference(self):
        self.context = 128
        process, report = self.invoke()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report['completed_exchanges'], 0)
        self.assertIn('context tokens', process.stderr)
        self.assertFalse(self.requests)

    def test_http_failure_saves_partial_report(self):
        self.fail_chat = True
        process, report = self.invoke()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report['message_count'], 0)
        self.assertIn('503', process.stderr)

    def test_invalid_host(self):
        for argument in ('host:0', 'host:65536', 'host:abc', 'http://host'):
            with self.subTest(argument=argument):
                process, report = self.invoke(argument)
                self.assertEqual(process.returncode, 2)
                self.assertIsNone(report)


    def test_duplicate_output_is_protected(self):
        path = Path(self.work.name) / 'existing.json'
        path.write_text('original')
        environment = dict(os.environ, BONSAI_BASE_URL=f'http://127.0.0.1:{self.server.server_port}',
                           BONSAI_BENCHMARK_RESULT=str(path))
        process = subprocess.run(['bash', str(PROJECT / 'simple_text_benchmark.sh')], env=environment,
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(path.read_text(), 'original')
        self.assertFalse(self.requests)

    def test_cancelled_run_preserves_status(self):
        self.delay_chat = True
        path = Path(self.work.name) / 'cancelled.json'
        environment = dict(os.environ, BONSAI_BASE_URL=f'http://127.0.0.1:{self.server.server_port}',
                           BONSAI_BENCHMARK_RESULT=str(path))
        process = subprocess.Popen(['bash', str(PROJECT / 'simple_text_benchmark.sh')], env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not self.requests and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.requests)
            process.send_signal(signal.SIGTERM)
            _, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, error)
            report = json.loads(path.read_text())
            self.assertEqual(report['status'], 'cancelled')
            self.assertEqual(report['completed_exchanges'], 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
