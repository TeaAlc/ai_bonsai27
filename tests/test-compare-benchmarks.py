#!/usr/bin/env -S python3 -B
"""Check weighted accounting and practical comparison review thresholds."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).parent

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TESTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

fixture = module('evidence_fixture', 'test-benchmark-evidence.py')
comparison = module('comparison', 'compare-benchmarks.py')


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.EvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.temp = tempfile.TemporaryDirectory(dir='/tmp/bonsai27')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for repetition in range(1, 4):
            for variant in ('baseline', 'candidate'):
                suite = f'{variant}-{repetition}'
                run = self.root / suite / 'run-1'
                shutil.copytree(self.fixture.root, run)
                minute = 2 * (repetition - 1) + (variant == 'candidate')
                identity = json.loads((run / 'identity.json').read_text())
                identity.update(suite_id=suite, run_id='run-1', container_id=suite,
                                captured_at=f'2026-10-02T10:0{minute}:00+00:00')
                identity['container']['Id'] = suite
                identity['argv'] += ['--spec-type', 'draft-mtp', '--spec-draft-n-max', '2']
                for name in ('identity.json', 'quality/identity.json'):
                    (run / name).write_text(json.dumps(identity))
                report = json.loads((run / 'benchmark.json').read_text())
                report.update(recorded_at=f'2026-10-02T10:0{minute}:10+00:00', reasoning_tokens_are_estimated=False)
                (run / 'benchmark.json').write_text(json.dumps(report))
                (run / 'gpu.csv').write_text(f'timestamp, memory.used [MiB]\n2026/10/02 10:0{minute}:05.000, 9000 MiB\n')
                fixture.module.finalize(run, 'completed', 0)

    def test_identical_comparison(self):
        result = comparison.compare(self.root)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['decode_change_percent'], 0)
        self.assertEqual(result['groups']['candidate']['cache_hit_rate_percent'], 50)
        self.assertTrue(result['identical_actual_requests'])

    def test_decode_regression_requires_review(self):
        for repetition in range(1, 4):
            run = self.root / f'candidate-{repetition}' / 'run-1'
            report = json.loads((run / 'benchmark.json').read_text())
            report['decode_tokens_per_second'] = 40
            (run / 'benchmark.json').write_text(json.dumps(report))
            for path in (run / 'benchmark/responses').glob('turn-*.json'):
                response = json.loads(path.read_text())
                response['timings']['predicted_ms'] = 500
                path.write_text(json.dumps(response))
            fixture.module.finalize(run, 'completed', 0)
        self.assertEqual(comparison.compare(self.root)['status'], 'review-required')

    def test_failed_run_is_not_averaged(self):
        fixture.module.finalize(self.root / 'candidate-2/run-1', 'failed', 1)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            comparison.compare(self.root)


if __name__ == '__main__':
    Path('/tmp/bonsai27').mkdir(parents=True, exist_ok=True)
    unittest.main()
