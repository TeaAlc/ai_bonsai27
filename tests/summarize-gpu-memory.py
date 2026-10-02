#!/usr/bin/env -S python3 -B
"""Summarize global GPU memory samples within a benchmark's measured interval."""
import sys
sys.dont_write_bytecode = True
import csv
import datetime
import json
import statistics
from pathlib import Path


def summarize(report, telemetry):
    # NVIDIA-SMI timestamps use the monitoring host's local time. Convert them
    # to aware instants before comparing against the benchmark's UTC timestamp.
    end = datetime.datetime.fromisoformat(report['recorded_at'])
    start = end - datetime.timedelta(seconds=report['wall_seconds'])
    samples = []
    for row in csv.DictReader(telemetry.splitlines(), skipinitialspace=True):
        try:
            instant = datetime.datetime.strptime(
                row['timestamp'], '%Y/%m/%d %H:%M:%S.%f').astimezone()
            used = int(row['memory.used [MiB]'].split()[0])
        except (KeyError, ValueError, TypeError):
            continue  # Unsupported NVML counters stay unknown, never zero.
        if start <= instant <= end:
            samples.append(used)
    return {
        'samples': len(samples),
        'sampling_interval_seconds': 1,
        'mean_used_mib': statistics.mean(samples) if samples else None,
        'peak_used_mib': max(samples) if samples else None,
        'minimum_used_mib': min(samples) if samples else None,
        'scope': 'Total GPU memory, including desktop and other processes; not per-container allocation.',
        'limitation': 'One-second sampling can miss shorter transient peaks.',
    }


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: summarize-gpu-memory.py <benchmark.json> <telemetry.csv> <output.json>')
    report_path, telemetry_path, output_path = map(Path, sys.argv[1:])
    data = summarize(json.loads(report_path.read_text()), telemetry_path.read_text())
    output_path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data, indent=2))
