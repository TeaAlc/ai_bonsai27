#!/usr/bin/env -S python3 -B
"""Reject tampering, mixed identities and incomplete benchmark evidence."""
import sys
sys.dont_write_bytecode = True
import copy
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark_evidence', ROOT / 'tests/benchmark_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/tmp/bonsai27')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identity = {'schema_version': 1, 'suite_id': 'suite', 'run_id': self.root.name,
                         'repetition': 1, 'image_id': 'sha256:fixture', 'container_id': 'container',
                         'captured_at': '2026-10-02T10:00:00+00:00',
                         'container': {'Image': 'sha256:fixture', 'Id': 'container'},
                         'props': {'default_generation_settings': {'n_ctx': 32000}},
                         'argv': ['server', '--ctx-size', '32000', '--flash-attn', 'on',
                                  '--override-tensor', '.*=CUDA0', '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0', '--no-mmproj-offload']}
        rows, messages = [], []
        for turn in range(1, 11):
            messages.append({'role': 'user', 'content': 'Question'})
            request = {'messages': copy.deepcopy(messages), 'reasoning_effort': 'medium',
                       'chat_template_kwargs': {'enable_thinking': True, 'reasoning_effort': 'medium'}}
            self.write(f'benchmark/requests/turn-{turn:02d}.json', request)
            messages.append({'role': 'assistant', 'content': 'Answer'})
            response = {'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                                  'completion_tokens_details': {'reasoning_tokens': 10}},
                        'choices': [{'finish_reason': 'stop', 'message': {'reasoning_content': 'Think'}}],
                        'timings': {'cache_n': 50, 'predicted_n': 20, 'predicted_ms': 400}}
            self.write(f'benchmark/responses/turn-{turn:02d}.json', response)
            rows.append({'exchange': turn, 'prompt_tokens': 100, 'completion_tokens': 20,
                         'cached_prompt_tokens': 50, 'reasoning_tokens': 10,
                         'reasoning_tokens_source': 'usage.completion_tokens_details.reasoning_tokens'})
        self.report = {'status': 'completed', 'completed_exchanges': 10, 'context_size': 32000,
                       'recorded_at': '2026-10-02T10:00:10+00:00', 'wall_seconds': 10,
                       'thinking_enabled': True, 'reasoning_effort': 'medium', 'messages': messages,
                       'exchanges': rows, 'prompt_tokens': 1000, 'completion_tokens': 200,
                       'total_tokens': 1200, 'cached_prompt_tokens': 500, 'reasoning_tokens': 100,
                       'cache_hit_rate_percent': 50, 'decode_tokens_per_second': 50,
                       'output_tokens_per_wall_second': 20}
        self.write('benchmark.json', self.report)
        self.write('identity.json', self.identity)
        self.write('quality/identity.json', self.identity)
        self.write('quality/quality/summary.json', {'data': [{'passed': True}] * 9})
        self.write('telemetry.json', {'timezone': 'UTC'})
        (self.root / 'gpu.csv').write_text('timestamp, memory.used [MiB]\n2026/10/02 10:00:05.000, 9000 MiB\n')
        self.write('gpu-memory.json', {'samples': 1, 'mean_used_mib': 9000,
                                     'peak_used_mib': 9000, 'minimum_used_mib': 9000})
        (self.root / 'server.log').write_text('fixture log')
        module.finalize(self.root, 'completed', 0)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_valid(self):
        self.assertEqual(module.audit(self.root)['status'], 'passed')

    def test_tampered_raw_artifacts(self):
        for name in ('server.log', 'gpu.csv', 'benchmark/responses/turn-01.json'):
            path = self.root / name
            original = path.read_bytes()
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed evidence'):
                module.audit(self.root)
            path.write_bytes(original)

    def test_escaped_path(self):
        index = json.loads((self.root / 'benchmark-index.json').read_text())
        index['files']['../escape'] = '0' * 64
        self.write('benchmark-index.json', index)
        with self.assertRaisesRegex(ValueError, 'Escaped'):
            module.audit(self.root)

    def test_wrong_image_and_container(self):
        for key in ('image_id', 'container_id', 'suite_id'):
            index = json.loads((self.root / 'benchmark-index.json').read_text())
            original = index[key]
            index[key] = 'other'
            self.write('benchmark-index.json', index)
            with self.assertRaisesRegex(ValueError, 'Mixed evidence'):
                module.audit(self.root)
            index[key] = original
            self.write('benchmark-index.json', index)

    def test_stale_and_mismatched_metrics(self):
        for key, value in (('recorded_at', '2025-01-01T00:00:00+00:00'),
                           ('reasoning_tokens', 101), ('cached_prompt_tokens', 501)):
            record = copy.deepcopy(self.report)
            record[key] = value
            self.write('benchmark.json', record)
            module.finalize(self.root, 'completed', 0)
            with self.assertRaises(ValueError):
                module.audit(self.root)
        self.write('benchmark.json', self.report)

    def test_partial_failure_is_not_acceptance(self):
        for status in ('running', 'failed', 'cancelled', 'timed-out'):
            module.finalize(self.root, status, 1)
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                module.audit(self.root)

    def test_wrong_request_policy(self):
        request = json.loads((self.root / 'benchmark/requests/turn-01.json').read_text())
        request['reasoning_effort'] = 'low'
        self.write('benchmark/requests/turn-01.json', request)
        module.finalize(self.root, 'completed', 0)
        with self.assertRaisesRegex(ValueError, 'reasoning mismatch'):
            module.audit(self.root)

    def test_bad_quality_and_vram(self):
        self.write('quality/quality/summary.json', {'data': [{'passed': False}] * 9})
        module.finalize(self.root, 'completed', 0)
        with self.assertRaisesRegex(ValueError, 'Quality probes'):
            module.audit(self.root)
        self.write('quality/quality/summary.json', {'data': [{'passed': True}] * 9})
        self.write('gpu-memory.json', {'samples': 1, 'mean_used_mib': 0,
                                     'peak_used_mib': 0, 'minimum_used_mib': 0})
        module.finalize(self.root, 'completed', 0)
        with self.assertRaisesRegex(ValueError, 'VRAM mismatch'):
            module.audit(self.root)


    def test_suite_and_duplicate_repetitions(self):
        with tempfile.TemporaryDirectory(dir='/tmp/bonsai27') as temporary:
            suite = Path(temporary) / 'suite'
            child = suite / 'run-1'
            shutil.copytree(self.root, child)
            identity = json.loads((child / 'identity.json').read_text())
            identity['run_id'] = 'run-1'
            (child / 'identity.json').write_text(json.dumps(identity))
            module.finalize(child, 'completed', 0)
            (suite / 'suite.json').write_text(json.dumps({'repetitions': 2}))
            module.suite_index(suite)
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                module.audit(suite)
            (suite / 'suite.json').write_text(json.dumps({'repetitions': 1}))
            module.suite_index(suite)
            self.assertEqual(module.audit(suite)['runs'], 1)
            shutil.copytree(child, suite / 'run-2')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                module.suite_index(suite)


    def test_podman_bare_and_prefixed_image_ids_match(self):
        identity = copy.deepcopy(self.identity)
        identity['container']['Image'] = 'fixture'
        self.write('identity.json', identity)
        module.finalize(self.root, 'completed', 0)
        self.assertEqual(module.audit(self.root)['status'], 'passed')


    def test_missing_thinking_tokenizer_evidence_is_rejected(self):
        report = copy.deepcopy(self.report)
        report['exchanges'][0]['reasoning_tokens_source'] = 'tokenizer.reasoning_content'
        self.write('benchmark.json', report)
        module.finalize(self.root, 'completed', 0)
        with self.assertRaisesRegex(ValueError, 'tokenizer evidence'):
            module.audit(self.root)

    def test_unknown_metrics_stay_null(self):
        report = copy.deepcopy(self.report)
        for row in report['exchanges']:
            response_path = f"benchmark/responses/turn-{row['exchange']:02d}.json"
            response = json.loads((self.root / response_path).read_text())
            response['timings'].pop('cache_n')
            response['timings'].pop('predicted_ms')
            response['usage'].pop('completion_tokens_details')
            self.write(response_path, response)
            row.update(cached_prompt_tokens=None, reasoning_tokens=None, reasoning_tokens_source=None)
        for key in ('cached_prompt_tokens', 'reasoning_tokens', 'cache_hit_rate_percent', 'decode_tokens_per_second'):
            report[key] = None
        self.write('benchmark.json', report)
        module.finalize(self.root, 'completed', 0)
        self.assertIsNone(module.audit(self.root)['reasoning_tokens'])


    def test_interrupted_quality_json_still_finalizes_failure(self):
        (self.root / 'quality/quality/summary.json').write_text('{partial')
        module.finalize(self.root, 'cancelled', 143, 'quality')
        index = json.loads((self.root / 'benchmark-index.json').read_text())
        self.assertEqual(index['status'], 'cancelled')
        self.assertEqual(index['failure_stage'], 'quality')
        self.assertEqual(index['exit_status'], 143)
        self.assertEqual(index['quality_status'], 'unknown')


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
