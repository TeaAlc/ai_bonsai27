#!/usr/bin/env -S python3 -B
"""Verify benchmark interval filtering and unknown GPU memory counters."""
import sys
sys.dont_write_bytecode = True
import datetime
import runpy
import unittest
from pathlib import Path

summarize = runpy.run_path(str(Path(__file__).with_name('summarize-gpu-memory.py')))['summarize']


class MemorySummaryTests(unittest.TestCase):
    def test_filters_startup_and_preserves_real_samples(self):
        end = datetime.datetime.now().astimezone()
        report = {'recorded_at': end.isoformat(), 'wall_seconds': 3}
        rows = ['timestamp, memory.used [MiB]']
        for offset, memory in ((-5, '9999 MiB'), (-2, '1200 MiB'),
                               (-1, '1400 MiB'), (1, '8888 MiB')):
            instant = end + datetime.timedelta(seconds=offset)
            rows.append(f'{instant:%Y/%m/%d %H:%M:%S.%f}, {memory}')
        result = summarize(report, '\n'.join(rows), 'Europe/Berlin')
        self.assertEqual(result['samples'], 2)
        self.assertEqual(result['mean_used_mib'], 1300)
        self.assertEqual(result['peak_used_mib'], 1400)

    def test_unknown_memory_is_null(self):
        report = {'recorded_at': datetime.datetime.now().astimezone().isoformat(), 'wall_seconds': 3}
        result = summarize(report, 'timestamp, memory.used [MiB]\ninvalid, N/A')
        self.assertEqual(result['samples'], 0)
        self.assertIsNone(result['peak_used_mib'])
        self.assertIsNone(result['mean_used_mib'])


    def test_short_rows_headers_and_zero(self):
        report = {'recorded_at': '2026-10-02T10:00:02+00:00', 'wall_seconds': 3}
        rows = 'timestamp, memory.used [MiB]\n2026-10-02T10:00:01+00:00, 0 MiB\n2026-10-02T10:00:01+00:00\ntimestamp, memory.used [MiB]\n, N/A\n'
        result = summarize(report, rows)
        self.assertEqual(result['samples'], 1)
        self.assertEqual(result['peak_used_mib'], 0)
        self.assertEqual(result['skipped_samples'], 3)

    def test_timezone_is_explicit_and_portable(self):
        report = {'recorded_at': '2026-10-02T10:00:02+00:00', 'wall_seconds': 3}
        rows = 'timestamp, memory.used [MiB]\n2026/10/02 12:00:01.000, 1200 MiB'
        self.assertIsNone(summarize(report, rows)['peak_used_mib'])
        self.assertEqual(summarize(report, rows, 'Europe/Berlin')['peak_used_mib'], 1200)
        self.assertIsNone(summarize(report, rows, 'UTC')['peak_used_mib'])

    def test_ambiguous_dst_is_rejected(self):
        report = {'recorded_at': '2026-10-25T02:00:00+00:00', 'wall_seconds': 7200}
        rows = 'timestamp, memory.used [MiB]\n2026/10/25 02:30:00.000, 100 MiB'
        self.assertIsNone(summarize(report, rows, 'Europe/Berlin')['peak_used_mib'])


    def test_explicit_offsets_are_safe_during_dst_fold(self):
        report = {'recorded_at': '2026-10-25T01:30:02+00:00', 'wall_seconds': 3}
        rows = 'timestamp, memory.used [MiB], memory.total [MiB]\n2026-10-25T02:30:01+01:00, 100 MiB, 12227 MiB'
        result = summarize(report, rows)
        self.assertEqual(result['peak_used_mib'], 100)
        self.assertEqual(result['capacity_mib'], 12227)

    def test_empty_missing_and_invalid_counters(self):
        report = {'recorded_at': '2026-10-02T10:00:02+00:00', 'wall_seconds': 3}
        for value in ('', 'N/A', '-1 MiB', 'not-a-number'):
            rows = 'timestamp, memory.used [MiB]\n2026-10-02T10:00:01+00:00, ' + value
            self.assertIsNone(summarize(report, rows)['peak_used_mib'])
        self.assertIsNone(summarize(report, 'timestamp\n2026-10-02T10:00:01+00:00')['peak_used_mib'])


if __name__ == '__main__':
    unittest.main()
