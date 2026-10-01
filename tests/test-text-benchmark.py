#!/usr/bin/env -S python3 -B
"""Exercise the real benchmark against a deterministic local HTTP fixture."""
import sys
sys.dont_write_bytecode = True
import json
import os
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
                self.wfile.write(body)

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
                    self.reply({'tokens': list(range(len(payload['content'].split())))})
                elif self.path == '/v1/chat/completions':
                    if fixture.fail_chat:
                        self.reply({'error': 'Fixture failure'}, 503)
                        return
                    fixture.requests.append(payload)
                    turn = len(fixture.requests)
                    answer = f'Exchange {turn}: retain the accessible entrance, quiet study area and durable library shelving.'
                    output_tokens = len(answer.split())
                    self.reply({
                        'usage': {'prompt_tokens': sum(len(message['content'].split()) for message in payload['messages']),
                                  'completion_tokens': output_tokens},
                        'choices': [{'message': {'content': answer}, 'finish_reason': 'stop'}],
                        'timings': {'predicted_n': output_tokens, 'predicted_ms': output_tokens * 20},
                    })
                else:
                    self.reply({}, 404)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def invoke(self, argument=None, base_suffix=''):
        result_path = Path(self.work.name) / 'report.json'
        environment = dict(os.environ, BONSAI_BASE_URL=f'http://127.0.0.1:{self.server.server_port}{base_suffix}',
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
        self.assertEqual(report['total_tokens'], report['prompt_tokens'] + report['completion_tokens'])
        self.assertEqual(report['decode_tokens_per_second'], 50)
        self.assertEqual(len(self.requests), 10)
        for index, payload in enumerate(self.requests):
            self.assertEqual(len(payload['messages']), index * 2 + 1)
            self.assertEqual(payload['messages'], report['messages'][:index * 2 + 1])
            self.assertEqual(payload['max_tokens'], 128)
            self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])
        self.assertIn('Message 20/20', process.stdout)

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


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
