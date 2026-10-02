#!/usr/bin/env -S python3 -B
"""Summarize global GPU memory inside an explicitly timezone-bound interval."""
import sys
sys.dont_write_bytecode = True
import csv
import datetime
import json
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo


def summarize(report, telemetry, timezone=None):
    end = datetime.datetime.fromisoformat(report['recorded_at'])
    if end.tzinfo is None:
        raise ValueError('Benchmark interval must have an explicit UTC offset')
    start = end - datetime.timedelta(seconds=report['wall_seconds'])
    samples, skipped, outside = [], 0, 0
    capacities = set()
    zone = ZoneInfo(timezone) if timezone else None
    for row in csv.DictReader(telemetry.splitlines(), skipinitialspace=True):
        try:
            stamp = row.get('timestamp')
            memory = row.get('memory.used [MiB]')
            if not isinstance(stamp, str) or not isinstance(memory, str):
                raise ValueError('Missing field')
            try:
                instant = datetime.datetime.fromisoformat(stamp)
            except ValueError:
                instant = datetime.datetime.strptime(stamp, '%Y/%m/%d %H:%M:%S.%f')
            if instant.tzinfo is None:
                if zone is None:
                    raise ValueError('Legacy telemetry needs an explicit timezone')
                # A legacy wall timestamp in a DST fold is ambiguous.
                if instant.replace(tzinfo=zone, fold=0).utcoffset() != instant.replace(tzinfo=zone, fold=1).utcoffset():
                    raise ValueError('Ambiguous DST timestamp')
                instant = instant.replace(tzinfo=zone)
            used = int(memory.split()[0])
            if used < 0:
                raise ValueError('Negative memory')
        except (KeyError, ValueError, TypeError, IndexError):
            skipped += 1
            continue
        if start <= instant <= end:
            samples.append(used)
            capacity = row.get('memory.total [MiB]')
            try:
                total = int(capacity.split()[0])
                if total > 0:
                    capacities.add(total)
            except (AttributeError, ValueError, IndexError):
                pass
        else:
            outside += 1
    return {
        'samples': len(samples), 'capacity_mib': next(iter(capacities)) if len(capacities) == 1 else None, 'skipped_samples': skipped,
        'outside_interval_samples': outside,
        'status': 'measured' if samples else 'unavailable',
        'timezone': timezone, 'interval_start': start.isoformat(), 'interval_end': end.isoformat(),
        'sampling_interval_seconds': 1,
        'mean_used_mib': statistics.mean(samples) if samples else None,
        'peak_used_mib': max(samples) if samples else None,
        'minimum_used_mib': min(samples) if samples else None,
        'scope': 'Total GPU memory, including desktop and other processes; not per-container allocation.',
        'limitation': 'One-second sampling can miss shorter transient peaks. Legacy timestamps require explicit timezone.',
    }


if __name__ == '__main__':
    if len(sys.argv) not in (4, 5):
        raise SystemExit('Usage: summarize-gpu-memory.py <benchmark.json> <telemetry.csv> <output.json> [legacy-timezone]')
    report_path, telemetry_path, output_path = map(Path, sys.argv[1:4])
    data = summarize(json.loads(report_path.read_text()), telemetry_path.read_text(),
                     sys.argv[4] if len(sys.argv) == 5 else None)
    output_path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data, indent=2))
