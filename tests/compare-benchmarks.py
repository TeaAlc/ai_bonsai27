#!/usr/bin/env -S python3 -B
"""Compare three alternating identified baseline/candidate benchmark suites."""
import sys
sys.dont_write_bytecode = True
import hashlib
import csv
import json
import statistics
from pathlib import Path
from benchmark_evidence import audit, atomic_json


def compare(root):
    root = Path(root)
    groups = {}
    requests = {}
    order = []
    containers = set()
    for variant in ('baseline', 'candidate'):
        rows = []
        for repetition in range(1, 4):
            run = root / f'{variant}-{repetition}' / 'run-1'
            verified = audit(run)
            report = json.loads((run / 'benchmark.json').read_text())
            memory = json.loads((run / 'gpu-memory.json').read_text())
            identity = json.loads((run / 'identity.json').read_text())
            if report['context_size'] != 32000:
                raise ValueError('Comparison requires exactly 32000 context tokens')
            if identity['container_id'] in containers:
                raise ValueError('Container reused across comparisons')
            containers.add(identity['container_id'])
            argv = identity['argv']
            if '--spec-type' not in argv or argv[argv.index('--spec-type') + 1] != 'draft-mtp' or argv[argv.index('--spec-draft-n-max') + 1] != '2':
                raise ValueError('Comparison requires MTP depth 2')
            idle_path = run / 'gpu-idle.csv'
            idle = {}
            if idle_path.exists():
                sample = next(csv.DictReader(idle_path.read_text().splitlines(), skipinitialspace=True), {})
                for field in ('memory.used [MiB]', 'utilization.gpu [%]', 'temperature.gpu'):
                    try:
                        idle[field] = int(sample[field].split()[0])
                    except (KeyError, TypeError, ValueError, IndexError):
                        idle[field] = None
                if idle.get('utilization.gpu [%]') is not None and idle['utilization.gpu [%]'] > 20:
                    raise ValueError('Competing GPU load invalidates comparison')
            payloads = [json.loads(path.read_text()) for path in sorted((run / 'benchmark/requests').glob('*.json'))]
            requests[variant, repetition] = payloads
            rows.append({**verified, 'wall_seconds': report['wall_seconds'],
                         'mean_used_mib': memory['mean_used_mib'], 'samples': memory['samples'],
                         'recorded_at': report['recorded_at'],
                         'output_sha256': hashlib.sha256(json.dumps(report['messages'], sort_keys=True).encode()).hexdigest(),
                         'thinking_tokens_are_estimated': report['reasoning_tokens_are_estimated'],
                         'idle_gpu': idle, 'evidence': str(run.relative_to(root))})
            order.append((report['recorded_at'], variant, repetition))
        groups[variant] = {'runs': rows}
        for key in ('decode_tokens_per_second', 'wall_seconds', 'peak_used_mib', 'reasoning_tokens'):
            values = [row[key] for row in rows]
            groups[variant][key] = {'mean': statistics.mean(values), 'sample_sd': statistics.stdev(values)} if all(v is not None for v in values) else None
        inputs = sum(row['prompt_tokens'] for row in rows)
        hits = [row['cached_prompt_tokens'] for row in rows]
        groups[variant]['cache_hit_rate_percent'] = round(100 * sum(hits) / inputs, 2) if all(hit is not None for hit in hits) else None
    observed_order = [(variant, repetition) for _, variant, repetition in sorted(order)]
    expected_order = [(variant, repetition) for repetition in range(1, 4) for variant in ('baseline', 'candidate')]
    if observed_order != expected_order:
        raise ValueError('Comparison was not alternated as planned')
    for repetition in range(1, 4):
        for baseline, candidate in zip(requests['baseline', repetition], requests['candidate', repetition]):
            for key in ('model', 'temperature', 'max_tokens', 'cache_prompt', 'reasoning_effort', 'chat_template_kwargs'):
                if baseline.get(key) != candidate.get(key):
                    raise ValueError('Effective request options differ: ' + key)
    baseline_speed = groups['baseline']['decode_tokens_per_second']['mean']
    candidate_speed = groups['candidate']['decode_tokens_per_second']['mean']
    change = 100 * (candidate_speed / baseline_speed - 1)
    memory_change = max(row['peak_used_mib'] for row in groups['candidate']['runs']) - max(row['peak_used_mib'] for row in groups['baseline']['runs'])
    return {'schema_version': 1, 'status': 'review-required' if change < -10 or memory_change > 256 else 'passed',
            'groups': groups, 'decode_change_percent': change,
            'peak_memory_change_mib': memory_change,
            'identical_actual_requests': all(requests['baseline', n] == requests['candidate', n] for n in range(1, 4)),
            'order': observed_order,
            'limits': 'Three runs on one WSL2 GPU; global VRAM includes desktop; no statistical confidence or full-window capacity claim.'}


if __name__ == '__main__':
    try:
        result = compare(sys.argv[1])
        atomic_json(Path(sys.argv[1]) / 'comparison.json', result)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['status'] == 'passed' else 1)
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
